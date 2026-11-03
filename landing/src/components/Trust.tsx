import { trust } from "../data/content";

export default function Trust() {
  return (
    <section className="section section--dark" id="trust">
      <div className="container">
        <div className="section__head reveal">
          <span className="eyebrow eyebrow--light">{trust.eyebrow}</span>
          <h2 className="section__title">{trust.title}</h2>
          <p className="section__intro section__intro--light">{trust.body}</p>
        </div>

        <div className="grid grid--3">
          {trust.pillars.map((p, i) => (
            <article className="pillar reveal" style={{ transitionDelay: `${i * 80}ms` }} key={p.title}>
              <h3 className="pillar__title">{p.title}</h3>
              <p className="pillar__desc">{p.desc}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
