import type { IconComponent } from "../../types";
import { PageHeader } from "../PageHeader/PageHeader";
import "./PlaceholderPage.css";

export function PlaceholderPage({
  icon: Icon,
  eyebrow = "Notice",
  title,
  description,
  chips,
}: {
  icon: IconComponent;
  eyebrow?: string;
  title: string;
  description: string;
  chips?: string[];
}) {
  return (
    <section className="blank-page">
      <PageHeader className="blank-page-header" icon={Icon} eyebrow={eyebrow} title={title} description={description} />
      {chips && chips.length > 0 && (
        <div className="placeholder-toolbar">
          {chips.map((chip) => (
            <span key={chip}>{chip}</span>
          ))}
        </div>
      )}
    </section>
  );
}
