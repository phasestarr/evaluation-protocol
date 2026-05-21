import csv
import re
from dataclasses import dataclass
from io import StringIO

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.postgres.models import (
    OrganizationImportUser,
    OrganizationMembership,
    OrganizationMembershipRole,
    OrganizationNode,
    OrganizationNodeType,
    PeerReviewTeam,
    SystemRole,
    User,
    UserWhitelist,
)
from app.services.organization import seed_root_organization
from app.services.text import normalize_email

settings = get_settings()

BEGIN_TOKEN = "BEGIN"
END_TOKEN = "END"
USER_ROW_TYPE = "______USER"
ASSIGNMENT_ROW_TYPE = "______ASSIGNMENT"
TREE_ROW_TYPES = {"COMPANY", "__HEAD", "____TEAM", USER_ROW_TYPE, ASSIGNMENT_ROW_TYPE}
USER_COLUMNS = ["attributes", "name", "title", "office_phone", "mobile", "email", "note"]
ROLE_BY_ATTRIBUTE = {
    "LEADER": OrganizationMembershipRole.leader,
    "MEMBER": OrganizationMembershipRole.member,
}
MOBILE_PATTERN = re.compile(r"^\d{3}-\d{4}-\d{4}$")


@dataclass(frozen=True)
class ParsedPerson:
    line_number: int
    attributes: str
    name: str
    title: str
    job_title: str | None
    office_phone: str
    mobile: str
    email: str
    note: str
    sort_order: int


@dataclass(frozen=True)
class ParsedMembership:
    line_number: int
    email: str
    node_key: tuple[str, ...]
    role: OrganizationMembershipRole


@dataclass(frozen=True)
class ParsedOrgNode:
    line_number: int
    node_key: tuple[str, ...]
    name: str
    node_type: OrganizationNodeType
    parent_key: tuple[str, ...] | None


@dataclass(frozen=True)
class ParsedOrganizationImport:
    company_name: str
    people: list[ParsedPerson]
    nodes: list[ParsedOrgNode]
    memberships: list[ParsedMembership]


def import_organization_csv(db: Session, content: bytes) -> dict:
    parsed = parse_organization_csv(content)
    apply_organization_import(db, parsed)
    return {
        "people": [serialize_import_person(person) for person in parsed.people],
    }


def parse_organization_csv(content: bytes) -> ParsedOrganizationImport:
    rows = parse_csv_block(content)
    if not rows:
        raise HTTPException(status_code=400, detail="BEGIN must be followed by COMPANY")

    first_line_number, first_row = rows[0]
    first_row = normalize_row(first_row, 2)
    if first_row[0] != "COMPANY":
        raise csv_error(first_line_number, "BEGIN must be followed by COMPANY")
    company_name = first_row[1].strip()
    if not company_name:
        raise csv_error(first_line_number, "COMPANY requires section")

    current_company: tuple[str, ...] | None = None
    current_head: tuple[str, ...] | None = None
    current_attach_node: tuple[str, ...] | None = None
    nodes: list[ParsedOrgNode] = []
    memberships: list[ParsedMembership] = []
    people: list[ParsedPerson] = []
    people_by_key: dict[tuple[str, str], ParsedPerson] = {}
    people_by_email: dict[str, ParsedPerson] = {}
    assignment_references: list[tuple[int, tuple[str, str]]] = []
    seen_node_keys: set[tuple[str, ...]] = set()

    for row_index, (line_number, raw_row) in enumerate(rows):
        row_type = raw_row[0].strip() if raw_row else ""
        if row_type not in TREE_ROW_TYPES:
            raise csv_error(line_number, f"Unsupported row_type: {row_type}")

        if row_type == "COMPANY":
            if row_index != 0:
                raise csv_error(line_number, "COMPANY is only allowed immediately after BEGIN")
            row = normalize_row(raw_row, 2)
            company_name = row[1].strip()
            if not company_name:
                raise csv_error(line_number, "COMPANY requires section")
            current_company = (company_name,)
            current_head = None
            current_attach_node = current_company
            nodes.append(
                ParsedOrgNode(
                    line_number=line_number,
                    node_key=current_company,
                    name=company_name,
                    node_type=OrganizationNodeType.company,
                    parent_key=None,
                )
            )
            seen_node_keys.add(current_company)
            continue

        if row_type == "__HEAD":
            if current_company is None:
                raise csv_error(line_number, "__HEAD requires a preceding COMPANY")
            head_name = require_group_name(raw_row, line_number, "__HEAD")
            current_head = (*current_company, head_name)
            current_attach_node = current_head
            add_node_once(nodes, seen_node_keys, line_number, current_head, head_name, OrganizationNodeType.head, current_company)
            continue

        if row_type == "____TEAM":
            if current_head is None:
                raise csv_error(line_number, "____TEAM requires a preceding __HEAD")
            team_name = require_group_name(raw_row, line_number, "____TEAM")
            current_attach_node = (*current_head, team_name)
            add_node_once(nodes, seen_node_keys, line_number, current_attach_node, team_name, OrganizationNodeType.team, current_head)
            continue

        if row_type in {USER_ROW_TYPE, ASSIGNMENT_ROW_TYPE}:
            if current_attach_node is None:
                raise csv_error(line_number, f"{row_type} requires a current organization node")
            person, role = parse_user_row(raw_row, line_number, len(people) + 1)
            person_key = (person.name, person.email)
            if row_type == USER_ROW_TYPE:
                if person_key in people_by_key:
                    raise csv_error(line_number, f"Duplicate {USER_ROW_TYPE}; use {ASSIGNMENT_ROW_TYPE} for additional memberships")
                if person.email in people_by_email:
                    raise csv_error(line_number, f"Duplicate email in {USER_ROW_TYPE} rows")
                people_by_key[person_key] = person
                people_by_email[person.email] = person
                people.append(person)
            else:
                assignment_references.append((line_number, person_key))
            memberships.append(ParsedMembership(line_number, person.email, current_attach_node, role))
            continue

    for line_number, person_key in assignment_references:
        if person_key not in people_by_key:
            raise csv_error(line_number, f"{ASSIGNMENT_ROW_TYPE} must reference a {USER_ROW_TYPE} in the same CSV by name and email")
    return ParsedOrganizationImport(company_name=company_name, people=people, nodes=nodes, memberships=memberships)


def parse_csv_block(content: bytes) -> list[tuple[int, list[str]]]:
    text = decode_csv_content(content)
    reader = csv.reader(StringIO(text))
    started = False
    ended = False
    rows: list[tuple[int, list[str]]] = []

    for line_number, raw_row in enumerate(reader, start=1):
        row = [value.strip() for value in raw_row]
        first_value = row[0] if row else ""
        if not started:
            if first_value == BEGIN_TOKEN:
                started = True
            continue
        if first_value == END_TOKEN:
            ended = True
            break
        if is_blank_row(row):
            raise csv_error(line_number, "Blank rows are not allowed between BEGIN and END")
        rows.append((line_number, row))

    if not started:
        raise HTTPException(status_code=400, detail="CSV must contain BEGIN")
    if not ended:
        raise HTTPException(status_code=400, detail="CSV must contain END")
    return rows


def decode_csv_content(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    raise HTTPException(status_code=400, detail="CSV must be a plain text file encoded as UTF-8 or CP949")


def normalize_row(raw_row: list[str], width: int) -> list[str]:
    values = [value.strip() for value in raw_row]
    if len(values) < width:
        values.extend([""] * (width - len(values)))
    return values


def is_blank_row(row: list[str]) -> bool:
    return all(not value.strip() for value in row)


def require_group_name(row: list[str], line_number: int, row_type: str) -> str:
    values = normalize_row(row, 2)
    name = values[1].strip()
    if not name:
        raise csv_error(line_number, f"{row_type} requires section")
    return name


def add_node_once(
    nodes: list[ParsedOrgNode],
    seen_node_keys: set[tuple[str, ...]],
    line_number: int,
    node_key: tuple[str, ...],
    name: str,
    node_type: OrganizationNodeType,
    parent_key: tuple[str, ...],
) -> None:
    if node_key in seen_node_keys:
        raise csv_error(line_number, f"Duplicate organization node: {' > '.join(node_key)}")
    nodes.append(ParsedOrgNode(line_number, node_key, name, node_type, parent_key))
    seen_node_keys.add(node_key)


def parse_user_row(row: list[str], line_number: int, sort_order: int) -> tuple[ParsedPerson, OrganizationMembershipRole]:
    values = normalize_row(row, 9)
    if values[1]:
        raise csv_error(line_number, "section must be empty for user rows")
    attribute, name, title, office_phone, mobile, email_value, note = [values[index].strip() for index in range(2, 9)]
    attribute = attribute.upper()
    role = ROLE_BY_ATTRIBUTE.get(attribute)
    if role is None:
        raise csv_error(line_number, "attributes must be LEADER or MEMBER")
    if not name:
        raise csv_error(line_number, "name is required")
    if mobile and not MOBILE_PATTERN.fullmatch(mobile):
        raise csv_error(line_number, "mobile must match 000-0000-0000")
    email = normalize_email(email_value)
    if not email:
        raise csv_error(line_number, "email is required")
    domain = settings.company_email_domain_normalized
    email_pattern = re.compile(rf"^[a-z0-9]+\.[a-z0-9]+@{re.escape(domain)}$")
    if not email_pattern.fullmatch(email):
        raise csv_error(line_number, f"email must match first.last@{domain}")
    person = ParsedPerson(
        line_number=line_number,
        attributes=attribute,
        name=name,
        title=title,
        job_title=parse_job_title(title),
        office_phone=office_phone,
        mobile=mobile,
        email=email,
        note=note,
        sort_order=sort_order,
    )
    return person, role


def parse_job_title(title: str) -> str | None:
    if not title.strip():
        return None
    return title.split("/")[-1].strip() or None


def apply_organization_import(db: Session, parsed: ParsedOrganizationImport) -> None:
    csv_emails = {person.email for person in parsed.people}
    try:
        seed_root_organization(db)
        root = db.scalar(
            select(OrganizationNode).where(
                OrganizationNode.node_type == OrganizationNodeType.company,
                OrganizationNode.parent_id.is_(None),
            )
        )
        if root is None:
            raise HTTPException(status_code=500, detail="Root organization node is not available")

        db.execute(delete(PeerReviewTeam))
        db.execute(delete(OrganizationImportUser))
        db.execute(delete(OrganizationMembership))
        non_root_nodes = db.scalars(
            select(OrganizationNode).where(
                ~(
                    (OrganizationNode.node_type == OrganizationNodeType.company)
                    & (OrganizationNode.parent_id.is_(None))
                )
            )
        ).all()
        for node in sorted(non_root_nodes, key=lambda item: item.id, reverse=True):
            db.delete(node)
        root.name = parsed.company_name
        db.flush()

        db.execute(delete(UserWhitelist).where(UserWhitelist.email != settings.initialization_email_normalized))
        user_delete = delete(User).where(User.email != settings.initialization_email_normalized)
        if csv_emails:
            user_delete = user_delete.where(User.email.not_in(csv_emails))
        db.execute(user_delete)
        db.flush()

        user_by_email = {
            user.email: user
            for user in db.scalars(select(User).where(User.email.in_(csv_emails))).all()
        } if csv_emails else {}
        for person in parsed.people:
            whitelist = db.scalar(select(UserWhitelist).where(UserWhitelist.email == person.email))
            if whitelist is None:
                db.add(UserWhitelist(email=person.email))
            user = user_by_email.get(person.email)
            if user is None:
                user = User(email=person.email, system_role=SystemRole.user)
                db.add(user)
                user_by_email[person.email] = user
            user.display_name = person.name
            user.job_title = person.job_title
        db.flush()

        for person in parsed.people:
            user = user_by_email[person.email]
            db.add(
                OrganizationImportUser(
                    user_id=user.id,
                    email=person.email,
                    attributes=person.attributes,
                    name=person.name,
                    title=person.title,
                    job_title=person.job_title,
                    office_phone=person.office_phone,
                    mobile=person.mobile,
                    note=person.note,
                    sort_order=person.sort_order,
                )
            )

        node_by_key: dict[tuple[str, ...], OrganizationNode] = {(parsed.company_name,): root}
        for parsed_node in parsed.nodes:
            if parsed_node.node_type == OrganizationNodeType.company:
                continue
            parent = node_by_key.get(parsed_node.parent_key)
            if parent is None:
                raise csv_error(parsed_node.line_number, "Parent organization node was not created")
            node = OrganizationNode(name=parsed_node.name, node_type=parsed_node.node_type, parent_id=parent.id)
            db.add(node)
            db.flush()
            node_by_key[parsed_node.node_key] = node

        seen_memberships: set[tuple[str, tuple[str, ...], OrganizationMembershipRole]] = set()
        for membership in parsed.memberships:
            membership_key = (membership.email, membership.node_key, membership.role)
            if membership_key in seen_memberships:
                continue
            seen_memberships.add(membership_key)
            user = user_by_email.get(membership.email)
            node = node_by_key.get(membership.node_key)
            if user is None or node is None:
                raise csv_error(membership.line_number, "Membership references missing user or organization node")
            db.add(
                OrganizationMembership(
                    user_id=user.id,
                    organization_node_id=node.id,
                    membership_role=membership.role,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise


def list_imported_users(db: Session) -> list[dict]:
    rows = db.scalars(select(OrganizationImportUser).order_by(OrganizationImportUser.sort_order, OrganizationImportUser.id)).all()
    return [serialize_import_user_row(row) for row in rows]


def serialize_import_user_row(row: OrganizationImportUser) -> dict:
    return {
        "line_number": row.sort_order,
        "attributes": row.attributes,
        "name": row.name,
        "title": row.title,
        "office_phone": row.office_phone,
        "mobile": row.mobile,
        "email": row.email,
        "note": row.note,
    }


def serialize_import_person(person: ParsedPerson) -> dict:
    return {
        "line_number": person.sort_order,
        "attributes": person.attributes,
        "name": person.name,
        "title": person.title,
        "office_phone": person.office_phone,
        "mobile": person.mobile,
        "email": person.email,
        "note": person.note,
    }


def csv_error(line_number: int, message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=f"Line {line_number}: {message}")
