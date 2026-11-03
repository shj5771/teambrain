"use client";

import { useReveal } from "./hooks/useReveal";
import Nav from "./components/Nav";
import Hero from "./components/Hero";
import ProblemSection from "./components/ProblemSection";
import FeatureDeck from "./components/FeatureDeck";
import Trust from "./components/Trust";
import Benefits from "./components/Benefits";
import Faq from "./components/Faq";
import Footer from "./components/Footer";

export default function App() {
  useReveal();

  return (
    <>
      <Nav />
      {/* 화면 단위로 딱딱 고정되는 스냅 스크롤 컨테이너 */}
      <div className="snap">
        <div className="panel">
          <Hero />
        </div>
        <div className="panel">
          <ProblemSection />
        </div>
        {/* 기능 ①~③ — 가로 슬라이드 (내부에 3화면) */}
        <FeatureDeck />
        <div className="panel">
          <Trust />
        </div>
        <div className="panel">
          <Benefits />
        </div>
        <div className="panel">
          <Faq />
        </div>
        <div className="panel panel--end">
          <Footer />
        </div>
      </div>
    </>
  );
}
