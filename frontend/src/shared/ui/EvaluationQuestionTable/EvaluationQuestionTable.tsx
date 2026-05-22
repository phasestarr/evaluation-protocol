import type { EvaluationQuestion } from "../../types";
import { MultilineText } from "../MultilineText/MultilineText";
import "./EvaluationQuestionTable.css";

export function EvaluationQuestionTable({
  questions,
  weighted,
  framed = false,
}: {
  questions: EvaluationQuestion[];
  weighted: boolean;
  framed?: boolean;
}) {
  if (questions.length === 0) return null;

  const table = (
    <div className="question-table-wrap">
      <table className="question-table">
        <colgroup>
          <col className="question-table-col-title" />
          <col className="question-table-col-description" />
          {weighted && <col className="question-table-col-weight" />}
          {weighted && <col className="question-table-col-effective" />}
        </colgroup>
        <thead>
          <tr>
            <th className="question-table-heading-title">항목</th>
            <th className="question-table-heading-description">설명</th>
            {weighted && <th className="question-table-heading-weight">가중치</th>}
            {weighted && <th className="question-table-heading-effective">유효가중치</th>}
          </tr>
        </thead>
        <tbody>
          {questions.map((question) => (
            <tr key={question.id}>
              <td className="question-table-cell-title">
                <strong>{question.title}</strong>
              </td>
              <td className="question-table-cell-description">
                <MultilineText text={question.description} />
              </td>
              {weighted && <td className="question-table-cell-weight">{question.weight}</td>}
              {weighted && <td className="question-table-cell-effective">{question.effective_weight_percent ?? 0}%</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  if (framed) {
    return <div className="question-table-frame">{table}</div>;
  }

  return table;
}
