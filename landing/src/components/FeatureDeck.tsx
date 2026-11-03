import { useEffect, useRef } from "react";
import InMessengerAI from "./InMessengerAI";
import TeamKnowledge from "./TeamKnowledge";
import PersonalAI from "./PersonalAI";

// 기능 ①~③을 가로로 이어붙인 슬라이드.
// 세로 스크롤로 이 구역을 지나가는 동안, 안쪽 트랙을 가로로 밀어서
// "스크롤하면 옆에서 다음 기능이 들어오는" 느낌을 만든다.
// (스크롤을 가로채지 않고, 세로 스크롤 위치를 가로 이동으로 바꾸는 방식이라
//  트랙패드·모바일에서도 안정적으로 동작한다.)
export default function FeatureDeck() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = sectionRef.current;
    const track = trackRef.current;
    if (!section || !track) return;

    const scroller = document.querySelector<HTMLElement>(".snap");
    if (!scroller) return;

    // 가로 슬라이드는 데스크톱(넓은 화면)에서만. 모바일에서는 세로로 폴백.
    // (모션 최소화 설정과 무관하게 넓은 화면에선 항상 가로로 동작시킨다.)
    const horizQuery = window.matchMedia("(min-width: 901px)");

    let raf = 0;
    const update = () => {
      raf = 0;
      if (!horizQuery.matches) {
        track.style.transform = "";
        return;
      }
      const rect = section.getBoundingClientRect();
      const total = section.offsetHeight - window.innerHeight; // 가로로 밀 수 있는 세로 스크롤 총량
      const scrolled = Math.min(Math.max(-rect.top, 0), Math.max(total, 0));
      const p = total > 0 ? scrolled / total : 0; // 0 → 1
      // 트랙은 화면 n개분 폭. 처음(화면1)에서 끝(화면n)까지 (n-1)/n 만큼 왼쪽으로 민다.
      const panels = track.children.length || 1;
      const maxPercent = ((panels - 1) / panels) * 100; // 3개면 66.67%
      track.style.transform = `translateX(${-(p * maxPercent)}%)`;
    };

    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };

    scroller.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();

    return () => {
      scroller.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="features" ref={sectionRef}>
      <div className="features__viewport">
        <div className="features__track" ref={trackRef}>
          <InMessengerAI />
          <TeamKnowledge />
          <PersonalAI />
        </div>
      </div>
    </div>
  );
}
