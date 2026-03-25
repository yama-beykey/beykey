import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useVideoConfig,
  interpolate,
  useCurrentFrame,
} from "remotion";

export type SubtitleItem = {
  startSec: number;
  endSec: number;
  text: string;
  textEn?: string;
};

export type TelopStyle = {
  fontFamily: string;
  fontSize: number;
  fontWeight: string;
  color: string;
  backgroundColor: string;
  borderRadius: number;
  paddingH: number;
  paddingV: number;
  position: "bottom" | "top";
  marginBottom: number;
};

const SingleCaption: React.FC<{
  item: SubtitleItem;
  durationInFrames: number;
  style: TelopStyle;
}> = ({ item, durationInFrames, style }) => {
  const frame = useCurrentFrame();
  const FADE_FRAMES = Math.min(5, Math.floor((durationInFrames - 1) / 2));

  const opacity =
    FADE_FRAMES > 0
      ? interpolate(
          frame,
          [0, FADE_FRAMES, durationInFrames - FADE_FRAMES, durationInFrames],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        )
      : 1;

  const translateY =
    FADE_FRAMES > 0
      ? interpolate(frame, [0, FADE_FRAMES], [12, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0;

  const isBottom = style.position !== "top";
  const enFontSize = Math.round(style.fontSize * 0.5);

  return (
    <AbsoluteFill
      style={{
        justifyContent: isBottom ? "flex-end" : "flex-start",
        alignItems: "center",
        paddingBottom: isBottom ? style.marginBottom : 0,
        paddingTop: isBottom ? 0 : 80,
        opacity,
        transform: `translateY(${translateY}px)`,
      }}
    >
      <div
        style={{
          maxWidth: "88%",
          background:
            "linear-gradient(160deg, rgba(4,4,18,0.90) 0%, rgba(12,12,32,0.90) 100%)",
          borderRadius: 18,
          paddingLeft: style.paddingH + 4,
          paddingRight: style.paddingH + 4,
          paddingTop: style.paddingV + 4,
          paddingBottom: style.paddingV + 4,
          border: "1px solid rgba(255,255,255,0.13)",
          boxShadow:
            "0 12px 40px rgba(0,0,0,0.55), 0 2px 8px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.08)",
          textAlign: "center",
        }}
      >
        {/* Japanese */}
        <div
          style={{
            fontFamily: style.fontFamily,
            fontSize: style.fontSize,
            fontWeight: style.fontWeight,
            color: style.color,
            lineHeight: 1.45,
            whiteSpace: "pre-wrap",
            letterSpacing: "0.03em",
            textShadow: "0 2px 8px rgba(0,0,0,0.75)",
          }}
        >
          {item.text}
        </div>

        {/* Divider + English */}
        {item.textEn && (
          <>
            <div
              style={{
                height: 1,
                background:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent)",
                margin: `${Math.round(style.paddingV * 0.55)}px 0`,
              }}
            />
            <div
              style={{
                fontFamily:
                  "'Noto Sans', 'Helvetica Neue', Arial, sans-serif",
                fontSize: enFontSize,
                fontWeight: 400,
                color: "rgba(185, 210, 255, 0.92)",
                lineHeight: 1.45,
                whiteSpace: "pre-wrap",
                letterSpacing: "0.025em",
                textShadow: "0 1px 5px rgba(0,0,0,0.6)",
              }}
            >
              {item.textEn}
            </div>
          </>
        )}
      </div>
    </AbsoluteFill>
  );
};

export const CaptionOverlay: React.FC<{
  subtitles: SubtitleItem[];
  telopStyle: TelopStyle;
}> = ({ subtitles, telopStyle }) => {
  const { fps } = useVideoConfig();

  const captionSequences = useMemo(
    () =>
      subtitles.map((sub) => {
        const startFrame = Math.round(sub.startSec * fps);
        const endFrame = Math.round(sub.endSec * fps);
        const durationInFrames = Math.max(endFrame - startFrame, 1);
        return { startFrame, durationInFrames, item: sub };
      }),
    [subtitles, fps]
  );

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {captionSequences.map((cap, i) => (
        <Sequence
          key={i}
          from={cap.startFrame}
          durationInFrames={cap.durationInFrames}
          layout="none"
        >
          <SingleCaption
            item={cap.item}
            durationInFrames={cap.durationInFrames}
            style={telopStyle}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
