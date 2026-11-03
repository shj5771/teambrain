import { inMessenger } from "../data/content";

export default function InMessengerAI() {
  return (
    <section className="section section--tint" id="in-messenger">
      <div className="container banner reveal">
        <div className="banner__text">
          <span className="eyebrow">{inMessenger.eyebrow}</span>
          <h2 className="section__title">{inMessenger.title}</h2>
          <p className="section__intro">{inMessenger.body}</p>
          <ul className="checklist">
            {inMessenger.points.map((p) => (
              <li key={p}>
                <span aria-hidden="true">✓</span> {p}
              </li>
            ))}
          </ul>
        </div>

        <div className="banner__visual">
          <div className="chat" aria-label="메신저에서 AI를 부르는 예시">
            <div className="chat__head">
              <span className="chat__dot" /> <span className="chat__dot" /> <span className="chat__dot" />
              <span className="chat__name"># 마케팅-팀</span>
            </div>
            <div className="chat__body">
              <div className="bubble bubble--user">{inMessenger.chat.user}</div>
              <div className="bubble bubble--bot">
                <span className="bubble__ai" aria-hidden="true">
                  🧠 AI
                </span>
                {inMessenger.chat.bot}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
