import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useVideoConfig,
  interpolate,
  useCurrentFrame,
  Img,
  staticFile,
} from "remotion";

export type SubtitleItem = {
  startSec: number;
  endSec: number;
  text: string;
  textEn?: string;
  highlight?: string[];  // words to color-highlight (uppercase match)
  emoji?: string;
  irasutoyaImage?: string;
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
  accentColor?: string;
};

// Render English text with per-word highlight support
const EnglishText: React.FC<{
  text: string;
  highlight?: string[];
  fontSize: number;
  fontFamily: string;
  accentColor: string;
}> = ({ text, highlight = [], fontSize, fontFamily, accentColor }) => {
  const words = text.split(/(\s+)/);
  const highlightSet = new Set(highlight.map((h) => h.toUpperCase()));

  const textOutline = [
    "2px 2px 0 rgba(0,0,0,0.95)",
    "-2px -2px 0 rgba(0,0,0,0.95)",
    "2px -2px 0 rgba(0,0,0,0.95)",
    "-2px 2px 0 rgba(0,0,0,0.95)",
    "0 4px 20px rgba(0,0,0,0.7)",
  ].join(", ");

  return (
    <div
      style={{
        fontFamily,
        fontSize,
        fontWeight: 900,
        lineHeight: 1.2,
        letterSpacing: "0.04em",
        textAlign: "center",
        textTransform: "uppercase",
        textShadow: textOutline,
      }}
    >
      {words.map((word, i) => {
        if (/^\s+$/.test(word)) return <span key={i}>{word}</span>;
        const clean = word.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
        const isHighlighted = highlightSet.has(clean);
        return (
          <span
            key={i}
            style={{
              color: isHighlighted ? accentColor : "#FFFFFF",
              display: "inline-block",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

const SingleCaption: React.FC<{
  item: SubtitleItem;
  durationInFrames: number;
  style: TelopStyle;
}> = ({ item, durationInFrames, style }) => {
  const frame = useCurrentFrame();
  const FADE = Math.min(5, Math.floor((durationInFrames - 1) / 2));

  const opacity =
    FADE > 0
      ? interpolate(
          frame,
          [0, FADE, durationInFrames - FADE, durationInFrames],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        )
      : 1;

  const scaleY = interpolate(frame, [0, FADE], [0.92, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const isBottom = style.position !== "top";
  const accentColor = style.accentColor ?? "#4AACFF";
  const jFontSize = Math.round(style.fontSize * 0.36);
  const emojiFontSize = Math.round(style.fontSize * 1.0);

  const jaOutline = [
    "1px 1px 0 rgba(0,0,0,0.9)",
    "-1px -1px 0 rgba(0,0,0,0.9)",
    "1px -1px 0 rgba(0,0,0,0.9)",
    "-1px 1px 0 rgba(0,0,0,0.9)",
    "0 2px 12px rgba(0,0,0,0.7)",
  ].join(", ");

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: isBottom ? "flex-end" : "flex-start",
        alignItems: "center",
        paddingBottom: isBottom ? style.marginBottom : 0,
        paddingTop: isBottom ? 0 : 80,
        paddingLeft: 32,
        paddingRight: 32,
        opacity,
        transform: `scaleY(${scaleY})`,
        transformOrigin: isBottom ? "bottom center" : "top center",
      }}
    >
      {/* Emoji */}
      {item.emoji && (
        <div
          style={{
            fontSize: emojiFontSize,
            lineHeight: 1,
            marginBottom: 8,
            filter: "drop-shadow(0 3px 8px rgba(0,0,0,0.6))",
          }}
        >
          {item.emoji}
        </div>
      )}

      {/* いらすとやイラスト（透過PNG切り抜き） */}
      {item.irasutoyaImage && (
        <Img
          src={staticFile(`project/${item.irasutoyaImage}`)}
          style={{
            width: 220,
            height: 220,
            objectFit: "contain",
            marginBottom: 12,
            filter:
              "drop-shadow(0 6px 16px rgba(0,0,0,0.6))" +
              " drop-shadow(0 2px 4px rgba(0,0,0,0.4))",
          }}
        />
      )}

      {/* English — primary, large, uppercase */}
      {item.textEn && (
        <EnglishText
          text={item.textEn}
          highlight={item.highlight}
          fontSize={style.fontSize}
          fontFamily={style.fontFamily}
          accentColor={accentColor}
        />
      )}

      {/* Japanese — secondary, small */}
      {item.text && (
        <div
          style={{
            fontFamily: style.fontFamily,
            fontSize: jFontSize,
            fontWeight: 500,
            color: "rgba(210, 225, 255, 0.88)",
            textShadow: jaOutline,
            marginTop: item.textEn ? 10 : 0,
            letterSpacing: "0.02em",
            lineHeight: 1.4,
            textAlign: "center",
          }}
        >
          {item.text}
        </div>
      )}
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
