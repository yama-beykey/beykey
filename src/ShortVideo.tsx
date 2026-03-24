/**
 * ShortVideo.tsx
 * Remotion公式Skillsのベストプラクティスに従った縦動画コンポジション
 * - 1080x1920 (縦動画 9:16)
 * - episode.jsonを読み込んでshotsをSequenceで時間順に配置
 * - Whisperタイムスタンプに同期したテロップ表示
 * - ショット間フェードトランジション（TransitionSeries）
 * - Ken Burns効果で静止画にモーション
 * - CSSアニメーション禁止 — useCurrentFrame + interpolate使用
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AbsoluteFill,
  Audio,
  continueRender,
  delayRender,
  Img,
  interpolate,
  Series,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  Video,
} from "remotion";
import {
  TransitionSeries,
  linearTiming,
} from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { loadFont } from "@remotion/google-fonts/NotoSansJP";
import { CaptionOverlay } from "./CaptionOverlay";
import type { SubtitleItem, TelopStyle } from "./CaptionOverlay";

// Noto Sans JP をロード（Remotion公式 fonts ルールに従う）
const { fontFamily } = loadFont();

// ===== 型定義 =====

export type ShotType = "video" | "image" | "color";

export type Shot = {
  id: string;
  startSec: number;
  endSec: number;
  type: ShotType;
  src?: string;
  videoStartSec?: number;
  videoEndSec?: number;
  backgroundColor?: string;
  label?: string;
};

export type EpisodeMeta = {
  title: string;
  pattern: string;
  tag: string;
  date: string;
  fps: number;
  width: number;
  height: number;
  durationSec: number;
};

export type EpisodeStyle = {
  telop: TelopStyle;
  title: {
    fontFamily: string;
    fontSize: number;
    fontWeight: string;
    color: string;
  };
  cta: {
    text: string;
    fontSize: number;
  };
  transition: {
    type: string;
    durationFrames: number;
  };
};

export type Episode = {
  meta: EpisodeMeta;
  files: {
    demoVideo: string | null;
    officialDemo: string | null;
    narration: string | null;
    screenshots: string[];
  };
  shots: Shot[];
  subtitles: SubtitleItem[];
  style: EpisodeStyle;
};

// ===== Ken Burns 静止画コンポーネント =====

const KenBurnsImage: React.FC<{ src: string; durationInFrames: number }> = ({
  src,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();

  // ゆっくりズームイン (1.0 → 1.08)
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.08], {
    extrapolateRight: "clamp",
  });
  // わずかに右上にパン
  const translateX = interpolate(
    frame,
    [0, durationInFrames],
    [0, -20],
    { extrapolateRight: "clamp" }
  );
  const translateY = interpolate(
    frame,
    [0, durationInFrames],
    [0, -15],
    { extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
          transformOrigin: "center center",
        }}
      />
    </AbsoluteFill>
  );
};

// ===== 単色背景コンポーネント =====

const ColorScene: React.FC<{
  backgroundColor: string;
  ctaText?: string;
  ctaFontSize?: number;
  durationInFrames: number;
}> = ({ backgroundColor, ctaText, ctaFontSize = 42, durationInFrames }) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 15, durationInFrames - 15, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const scale = interpolate(frame, [0, 20], [0.85, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      {ctaText && (
        <div
          style={{
            opacity,
            transform: `scale(${scale})`,
            fontFamily,
            fontSize: ctaFontSize,
            fontWeight: "900",
            color: "#FFFFFF",
            textAlign: "center",
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
            padding: "0 60px",
          }}
        >
          {ctaText}
        </div>
      )}
    </AbsoluteFill>
  );
};

// ===== ビデオショットコンポーネント =====

const VideoShot: React.FC<{
  src: string;
  startOffsetSec: number;
  durationInFrames: number;
}> = ({ src, startOffsetSec, durationInFrames }) => {
  const { fps } = useVideoConfig();
  const startOffsetInFrames = Math.round(startOffsetSec * fps);

  return (
    <AbsoluteFill>
      <Video
        src={src}
        startFrom={startOffsetInFrames}
        endAt={startOffsetInFrames + durationInFrames}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </AbsoluteFill>
  );
};

// ===== メインコンポジション =====

export const ShortVideo: React.FC = () => {
  const { fps } = useVideoConfig();

  const [episode, setEpisode] = useState<Episode | null>(null);
  const [handle] = useState(() => delayRender("Loading episode.json"));

  const fetchEpisode = useCallback(async () => {
    try {
      const res = await fetch(staticFile("project/episode.json"));
      const data: Episode = await res.json();
      setEpisode(data);
      continueRender(handle);
    } catch (e) {
      continueRender(handle);
    }
  }, [handle]);

  useEffect(() => {
    fetchEpisode();
  }, [fetchEpisode]);

  if (!episode) {
    return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
  }

  const { shots, subtitles, style, files } = episode;
  const transitionDurationFrames = style.transition.durationFrames ?? 8;

  // ショットごとのフレーム尺を計算
  const shotDurations = shots.map((shot) => {
    const rawFrames = Math.round((shot.endSec - shot.startSec) * fps);
    // 最小1フレーム保証
    return Math.max(rawFrames, 1);
  });

  // テロップスタイルにロードしたフォントを適用
  const telopStyle: TelopStyle = {
    ...style.telop,
    fontFamily,
  };

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* ナレーション音声 */}
      {files.narration && (
        <Audio src={staticFile(`project/${files.narration}`)} />
      )}

      {/* 映像レイヤー: TransitionSeriesでフェードトランジション */}
      <TransitionSeries>
        {shots.map((shot, i) => {
          const durationInFrames = shotDurations[i];
          const isLast = i === shots.length - 1;

          const sceneElement = (() => {
            if (shot.type === "video" && shot.src) {
              return (
                <VideoShot
                  src={staticFile(`project/${shot.src}`)}
                  startOffsetSec={shot.videoStartSec ?? 0}
                  durationInFrames={durationInFrames}
                />
              );
            }
            if (shot.type === "image" && shot.src) {
              return (
                <KenBurnsImage
                  src={staticFile(`project/${shot.src}`)}
                  durationInFrames={durationInFrames}
                />
              );
            }
            // type === "color" (CTAなど)
            const isCta = shot.id === "cta";
            return (
              <ColorScene
                backgroundColor={shot.backgroundColor ?? "#1a1a2e"}
                ctaText={isCta ? style.cta.text : undefined}
                ctaFontSize={style.cta.fontSize}
                durationInFrames={durationInFrames}
              />
            );
          })();

          return (
            <React.Fragment key={shot.id}>
              <TransitionSeries.Sequence
                durationInFrames={durationInFrames}
              >
                {sceneElement}
              </TransitionSeries.Sequence>
              {/* 最後のショット以外にフェードトランジションを挿入 */}
              {!isLast && (
                <TransitionSeries.Transition
                  presentation={fade()}
                  timing={linearTiming({
                    durationInFrames: transitionDurationFrames,
                  })}
                />
              )}
            </React.Fragment>
          );
        })}
      </TransitionSeries>

      {/* テロップレイヤー: 映像の上に重ねる */}
      <CaptionOverlay subtitles={subtitles} telopStyle={telopStyle} />
    </AbsoluteFill>
  );
};
