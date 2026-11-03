import { problem } from "../data/content";

export default function ProblemSection() {
  return (
    <section className="section" id="problem">
      <div className="container">
        <div className="section__head reveal">
          <span className="eyebrow">{problem.eyebrow}</span>
          <h2 className="section__title">{problem.title}</h2>
          <p className="section__intro">
            {problem.introLines.map((line, i) => (
              <span key={line}>
                {line}
                {i < problem.introLines.length - 1 && <br />}
              </span>
            ))}
          </p>
        </div>

        <div className="grid grid--3">
          {problem.cards.map((c, i) => (
            <article className="card card--problem reveal" style={{ transitionDelay: `${i * 80}ms` }} key={c.title}>
              <div className="card__icon" aria-hidden="true">
                {c.icon}
              </div>
              <h3 className="card__title">{c.title}</h3>
              <p className="card__body">{c.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
