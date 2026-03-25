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
  text: string;
  durationInFrames: number;
  style: TelopStyle;
}> = ({ text, durationInFrames, style }) => {
  const frame = useCurrentFrame();
  const FADE_FRAMES = Math.min(4, Math.floor((durationInFrames - 1) / 2));

  const opacity =
    FADE_FRAMES > 0
      ? interpolate(
          frame,
          [0, FADE_FRAMES, durationInFrames - FADE_FRAMES, durationInFrames],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        )
      : 1;

  return (
    <AbsoluteFill
      style={{
        justifyContent: style.position === "bottom" ? "flex-end" : "flex-start",
        alignItems: "center",
        paddingBottom: style.position === "bottom" ? style.marginBottom : 0,
        paddingTop: style.position === "top" ? 80 : 0,
        opacity,
      }}
    >
      <div
        style={{
          fontFamily: style.fontFamily,
          fontSize: style.fontSize,
          fontWeight: style.fontWeight,
          color: style.color,
          backgroundColor: style.backgroundColor,
          borderRadius: style.borderRadius,
          paddingLeft: style.paddingH,
          paddingRight: style.paddingH,
          paddingTop: style.paddingV,
          paddingBottom: style.paddingV,
          maxWidth: "90%",
          textAlign: "center",
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
        }}
      >
        {text}
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
        return { startFrame, durationInFrames, text: sub.text };
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
            text={cap.text}
            durationInFrames={cap.durationInFrames}
            style={telopStyle}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
