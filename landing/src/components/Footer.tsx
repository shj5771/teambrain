import { finalCta, footer, brand } from "../data/content";

export default function Footer() {
  return (
    <>
      <section className="cta" id="cta">
        <div className="container cta__inner reveal">
          <h2 className="cta__title">{finalCta.title}</h2>
          <p className="cta__body">{finalCta.body}</p>
          <a className="btn btn--lg" href="#top">
            {finalCta.cta}
          </a>
        </div>
      </section>

      <footer className="footer">
        <div className="container footer__inner">
          <div className="footer__brand">
            <span className="nav__logo-mark" aria-hidden="true">
              🧠
            </span>
            <strong>{brand.name}</strong>
          </div>
          <p className="footer__note">{footer.note}</p>
        </div>
      </footer>
    </>
  );
}
