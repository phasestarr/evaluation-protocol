import { useEffect, useMemo, useState } from "react";
import { saveSelfReviewAnswer, fetchSelfReview } from "../api";
import { EvaluationQuestionTable } from "../components/EvaluationQuestionTable";
import { MarkdownBlock } from "../components/MarkdownBlock";
import { StatusMessage } from "../components/StatusMessage";
import type { EvaluationQuestion, SelfReviewResponse } from "../types";

const ANSWER_LIMIT = 1000;

export function SelfReviewPage() {
  const [data, setData] = useState<SelfReviewResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const questions = useMemo(() => data?.questions ?? [], [data?.questions]);

  useEffect(() => {
    fetchSelfReview()
      .then((result) => {
        setData(result);
        setDrafts(
          Object.fromEntries(
            result.questions.map((question) => [question.id, result.answers[String(question.id)] ?? ""]),
          ),
        );
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "자기평가를 불러오지 못했습니다."));
  }, []);

  async function saveAnswer(question: EvaluationQuestion) {
    const value = drafts[question.id] ?? "";
    if (value.length > ANSWER_LIMIT) {
      setMessage("답변은 1000자 이하로 입력해 주세요.");
      return;
    }
    setMessage(null);
    try {
      await saveSelfReviewAnswer(question.id, value);
      setMessage("저장되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "답변을 저장하지 못했습니다.");
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Self Review</p>
        <h1>자기평가</h1>
        <MarkdownBlock content={data?.guide_content || "문항 설명이 등록되지 않았습니다. 관리자에게 문의하세요."} />
        <EvaluationQuestionTable questions={questions} weighted={false} framed />
      </div>
      <StatusMessage message={message} />
      <div className="evaluation-stack">
        {questions.map((question) => {
          const value = drafts[question.id] ?? "";
          return (
            <section className="surface-panel evaluation-question-panel" key={question.id}>
              <div>
                <h2>{question.title}</h2>
                {question.description && <p>{question.description}</p>}
              </div>
              <textarea
                maxLength={ANSWER_LIMIT}
                value={value}
                onChange={(event) => setDrafts((current) => ({ ...current, [question.id]: event.target.value }))}
              />
              <div className="question-action-row">
                <span>
                  {value.length}/{ANSWER_LIMIT}
                </span>
                <button className="inline-button" type="button" onClick={() => saveAnswer(question)}>
                  저장
                </button>
              </div>
            </section>
          );
        })}
        {data && questions.length === 0 && <p className="empty-copy">등록된 자기평가 문항이 없습니다.</p>}
      </div>
    </section>
  );
}
