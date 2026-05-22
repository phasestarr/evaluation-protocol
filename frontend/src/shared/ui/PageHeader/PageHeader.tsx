import type { ReactNode } from "react";
import type { IconComponent } from "../../types";
import "./PageHeader.css";

export function PageHeader({
  icon: Icon,
  thumbPlacement = "inline",
  descriptionPlacement = "inline",
  childrenPlacement = "inline",
  eyebrow,
  title,
  description,
  aside,
  children,
  className,
}: {
  icon?: IconComponent;
  thumbPlacement?: "inline" | "top";
  descriptionPlacement?: "inline" | "full-width";
  childrenPlacement?: "inline" | "full-width";
  eyebrow: string;
  title: string;
  description?: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={["page-header", className].filter(Boolean).join(" ")}>
      <div className="page-header-top">
        <div
          className={[
            "page-header-main",
            Icon ? "with-thumb" : "without-thumb",
            thumbPlacement === "top" ? "thumb-top" : "thumb-inline",
          ].join(" ")}
        >
          {Icon && (
            <div className="page-header-thumb" aria-hidden="true">
              <Icon size={32} />
            </div>
          )}
          <div className="page-header-copy">
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            {descriptionPlacement === "inline" && description ? <div className="page-header-description">{description}</div> : null}
            {childrenPlacement === "inline" ? children : null}
          </div>
        </div>
        {aside && <div className="page-header-aside">{aside}</div>}
      </div>
      {(descriptionPlacement === "full-width" && description) || (childrenPlacement === "full-width" && children) ? (
        <div className="page-header-support">
          {descriptionPlacement === "full-width" && description ? <div className="page-header-description">{description}</div> : null}
          {childrenPlacement === "full-width" && children ? children : null}
        </div>
      ) : null}
    </div>
  );
}
