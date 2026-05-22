import { Fragment } from "react";

export function MultilineText({ text }: { text: string | null | undefined }) {
  if (!text) {
    return null;
  }

  const lines = text.split(/\r?\n/);
  return (
    <>
      {lines.map((line, index) => (
        <Fragment key={index}>
          {index > 0 ? <br /> : null}
          {line}
        </Fragment>
      ))}
    </>
  );
}
