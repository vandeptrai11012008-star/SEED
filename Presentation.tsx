import { useEffect } from "react";
import { SLIDES, useStore } from "../store";

// Guided slide-by-slide scene tour. Each slide flies the camera to a preset
// (CameraRig lerps smoothly) and sets the matching overlay/cutaway, so stepping
// through slides reads like a cinematic presentation.
export default function Presentation() {
  const presenting = useStore((s) => s.presenting);
  const slideIndex = useStore((s) => s.slideIndex);
  const autoAdvance = useStore((s) => s.autoAdvance);
  const next = useStore((s) => s.nextSlide);
  const prev = useStore((s) => s.prevSlide);
  const goTo = useStore((s) => s.goToSlide);
  const stop = useStore((s) => s.stopPresentation);
  const setAutoAdvance = useStore((s) => s.setAutoAdvance);

  // Keyboard: arrows to navigate, Escape to exit. Disabled during walkthrough
  // so WASD/look keys are not intercepted.
  useEffect(() => {
    if (!presenting) return;
    const onKey = (e: KeyboardEvent) => {
      if (SLIDES[slideIndex]?.camera === "walkthrough") return;
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "Escape") stop();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [presenting, slideIndex, next, prev, stop]);

  // Auto-advance timer (dwell on each slide, loop at the end).
  useEffect(() => {
    if (!presenting || !autoAdvance) return;
    const id = setTimeout(() => {
      const current = useStore.getState().slideIndex;
      goTo((current + 1) % SLIDES.length);
    }, 6500);
    return () => clearTimeout(id);
  }, [presenting, autoAdvance, slideIndex, goTo]);

  if (!presenting) return null;
  const slide = SLIDES[slideIndex];
  const isLast = slideIndex === SLIDES.length - 1;

  return (
    <div className="presentation">
      <div className="presentation-caption">
        <div className="presentation-progress">
          Scene {slideIndex + 1} / {SLIDES.length}
        </div>
        <h2>{slide.title}</h2>
        {slide.subtitle && <div className="presentation-subtitle">{slide.subtitle}</div>}
        <p>{slide.description}</p>
        {slide.points && slide.points.length > 0 && (
          <ul className="presentation-points">
            {slide.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        )}
        <div className="presentation-dots">
          {SLIDES.map((s, i) => (
            <button
              key={s.id}
              className={`dot ${i === slideIndex ? "active" : ""}`}
              title={s.title}
              onClick={() => goTo(i)}
            />
          ))}
        </div>
      </div>

      <div className="presentation-controls">
        <button className="secondary" onClick={prev} disabled={slideIndex === 0}>
          ‹ Prev
        </button>
        <button
          className={autoAdvance ? "active" : "secondary"}
          onClick={() => setAutoAdvance(!autoAdvance)}
        >
          {autoAdvance ? "Auto ▮▮" : "Auto ▶"}
        </button>
        {isLast ? (
          <button className="secondary" onClick={() => goTo(0)}>Restart ↺</button>
        ) : (
          <button onClick={next}>Next ›</button>
        )}
        <button className="secondary exit" onClick={stop} title="Exit presentation (Esc)">
          Exit
        </button>
      </div>
    </div>
  );
}
