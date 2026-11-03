import { hero } from "../data/content";

export default function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero__bg" aria-hidden="true" />
      <div className="container hero__inner reveal">
        <h1 className="hero__title">
          {hero.title[0]}
          <br />
          <span className="grad-text">{hero.title[1]}</span>
        </h1>

        <p className="hero__subtitle">{hero.subtitle}</p>

        <div className="hero__actions">
          <a className="btn" href="#in-messenger">
            {hero.primaryCta}
          </a>
          <a className="btn btn--ghost" href="#benefits">
            {hero.secondaryCta}
          </a>
        </div>

        <ul className="hero__badges">
          {hero.trustBadges.map((b) => (
            <li key={b}>
              <span aria-hidden="true">✓</span> {b}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
