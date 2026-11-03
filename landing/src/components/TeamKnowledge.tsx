import { teamKnowledge as t } from "../data/content";

export default function TeamKnowledge() {
  return (
    <section className="section" id="team-knowledge">
      <div className="container banner reveal">
        <div className="banner__text">
          <span className="eyebrow">{t.eyebrow}</span>
          <h2 className="section__title">{t.title}</h2>
          <p className="section__intro">{t.body}</p>
          <ul className="checklist">
            {t.points.map((p) => (
              <li key={p}>
                <span aria-hidden="true">✓</span> {p}
              </li>
            ))}
          </ul>
        </div>

        <div className="banner__visual">
          <div className="chat" aria-label="새 팀원이 팀 지식을 검색하는 예시">
            <div className="chat__head">
              <span className="chat__dot" /> <span className="chat__dot" /> <span className="chat__dot" />
              <span className="chat__name">👋 새 팀원</span>
            </div>
            <div className="chat__body">
              <div className="bubble bubble--user">{t.chat.user}</div>
              <div className="bubble bubble--bot">
                <span className="bubble__ai" aria-hidden="true">
                  🧠 AI
                </span>
                {t.chat.bot}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="container">
        <details className="detail-toggle reveal">
          <summary>{t.detail.toggleLabel}</summary>
          <div className="split detail-toggle__body">
            <div className="split__col">
              <h3 className="subhead">{t.detail.how.title}</h3>
              <ol className="flow">
                {t.detail.how.steps.map((s, i) => (
                  <li className="flow__item" key={i}>
                    <span className="flow__num">{i + 1}</span>
                    <p>{s}</p>
                  </li>
                ))}
              </ol>
            </div>

            <div className="split__col">
              <h3 className="subhead">{t.detail.compare.title}</h3>
              <div className="compare">
                <div className="compare__labels">
                  <span className="compare__label compare__label--before">{t.detail.compare.beforeLabel}</span>
                  <span className="compare__label compare__label--after">{t.detail.compare.afterLabel}</span>
                </div>
                {t.detail.compare.rows.map((r, i) => (
                  <div className="compare__row" key={i}>
                    <div className="compare__before">
                      <span aria-hidden="true">✕</span> {r.before}
                    </div>
                    <div className="compare__arrow" aria-hidden="true">
                      →
                    </div>
                    <div className="compare__after">
                      <span aria-hidden="true">✓</span> {r.after}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </details>
      </div>
    </section>
  );
}
