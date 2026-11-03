import { useState } from "react";
import { faq } from "../data/content";

export default function Faq() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="section section--tint" id="faq">
      <div className="container container--narrow">
        <div className="section__head reveal">
          <span className="eyebrow">{faq.eyebrow}</span>
          <h2 className="section__title">{faq.title}</h2>
        </div>

        <ul className="faq reveal">
          {faq.items.map((item, i) => {
            const isOpen = open === i;
            return (
              <li className={`faq__item ${isOpen ? "is-open" : ""}`} key={i}>
                <button
                  className="faq__q"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : i)}
                >
                  <span>{item.q}</span>
                  <span className="faq__icon" aria-hidden="true">
                    {isOpen ? "−" : "+"}
                  </span>
                </button>
                <div className="faq__a" hidden={!isOpen}>
                  <p>{item.a}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
