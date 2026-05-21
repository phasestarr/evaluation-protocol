import type { IconComponent } from "../../types";
import "./PlaceholderPage.css";

export function PlaceholderPage({
  icon: Icon,
  title,
  description,
  chips,
}: {
  icon: IconComponent;
  title: string;
  description: string;
  chips?: string[];
}) {
  return (
    <section className="blank-page">
      <Icon size={34} />
      <h1>{title}</h1>
      <p>{description}</p>
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
