import { personalAI as p } from "../data/content";

export default function PersonalAI() {
  return (
    <section className="section section--tint" id="personal-ai">
      <div className="container banner reveal">
        <div className="banner__text">
          <span className="eyebrow">{p.eyebrow}</span>
          <h2 className="section__title">{p.title}</h2>
          <p className="section__intro">{p.body}</p>
          <ul className="checklist">
            {p.points.map((pt) => (
              <li key={pt}>
                <span aria-hidden="true">✓</span> {pt}
              </li>
            ))}
          </ul>
        </div>

        <div className="banner__visual">
          <div className="chat chat--personal" aria-label="개인 AI와 대화하는 예시">
            <div className="chat__head">
              <span className="chat__dot" /> <span className="chat__dot" /> <span className="chat__dot" />
              <span className="chat__name">💬 나의 AI</span>
            </div>
            <div className="chat__body">
              <div className="bubble bubble--user">{p.chat.user}</div>
              <div className="bubble bubble--bot">
                <span className="bubble__ai" aria-hidden="true">
                  🧠 AI
                </span>
                {p.chat.bot}
              </div>
            </div>
          </div>
          <p className="footnote">{p.footnote}</p>
        </div>
      </div>

      <div className="container">
        <details className="detail-toggle reveal">
          <summary>{p.detail.toggleLabel}</summary>
          <ul className="detail-list detail-toggle__body">
            {p.detail.items.map((it) => (
              <li className="detail-list__item" key={it.title}>
                <span className="detail-list__icon" aria-hidden="true">
                  {it.icon}
                </span>
                <div>
                  <h3 className="detail-list__title">{it.title}</h3>
                  <p className="detail-list__body">{it.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </section>
  );
}
