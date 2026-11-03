import { brand } from "../data/content";

export default function Nav() {
  return (
    <header className="nav">
      <div className="nav__inner">
        <a className="nav__logo" href="#top" aria-label={`${brand.name} 홈`}>
          <span className="nav__logo-mark" aria-hidden="true">
            🧠
          </span>
          <span className="nav__logo-text">
            {brand.name}
            <em>{brand.tagline}</em>
          </span>
        </a>

        <nav className="nav__links" aria-label="주요 섹션">
          <a href="#in-messenger">기능</a>
          <a href="#trust">신뢰</a>
          <a href="#faq">자주 묻는 질문</a>
        </nav>

        <a className="btn btn--sm" href="#cta">
          도입 문의
        </a>
      </div>
    </header>
  );
}
