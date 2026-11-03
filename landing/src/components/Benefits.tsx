import { benefits as b } from "../data/content";

export default function Benefits() {
  return (
    <section className="section section--slim" id="benefits">
      <div className="container">
        <div className="section__head reveal">
          <span className="eyebrow">{b.eyebrow}</span>
          <h2 className="section__title">{b.title}</h2>
        </div>

        <ul className="chips reveal">
          {b.items.map((it) => (
            <li className="chip" key={it.title}>
              <span aria-hidden="true">{it.icon}</span> {it.title}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
