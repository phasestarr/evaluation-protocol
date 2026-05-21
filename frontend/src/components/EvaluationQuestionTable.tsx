import type { EvaluationQuestion } from "../types";

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
        <thead>
          <tr>
            <th>항목</th>
            <th>설명</th>
            {weighted && <th>가중치</th>}
            {weighted && <th>유효가중치</th>}
          </tr>
        </thead>
        <tbody>
          {questions.map((question) => (
            <tr key={question.id}>
              <td>{question.title}</td>
              <td>{question.description}</td>
              {weighted && <td>{question.weight}</td>}
              {weighted && <td>{question.effective_weight_percent ?? 0}%</td>}
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
