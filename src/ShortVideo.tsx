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
import { CaptionOverlay } from "./CaptionOverlay";
import type { SubtitleItem, TelopStyle } from "./CaptionOverlay";
import { AutoZoom } from "./AutoZoom";
import type { ActionPoint } from "./AutoZoom";

// Noto Sans JP フォント名（レンダリング環境にフォントがインストール済みの場合はこのまま使用）
// ネットワーク接続がある環境では loadFont() を呼ぶことでWebフォントを確実に読み込める:
//   import { loadFont } from "@remotion/google-fonts/NotoSansJP";
//   loadFont("normal", { subsets: ["[0]","[1]","[2]"], weights: ["400","700","900"] });
import { fontFamily as notoFontFamily } from "@remotion/google-fonts/NotoSansJP";
const fontFamily = `${notoFontFamily}, 'Hiragino Sans', 'Yu Gothic', sans-serif`;

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

export type OverlayConfig = {
  topHeight: number;
  bottomHeight: number;
  topColor: string;
  bottomColor: string;
  logoText?: string;
  logoFontSize?: number;
  logoColor?: string;
  logoImage?: string;
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
  overlay?: OverlayConfig;
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
  /** actions_timeline.json から生成されたズームタイムライン (省略可) */
  actionsTimeline?: ActionPoint[];
  /**
   * AI生成クリップマップ: shot.id → "ai-clips/ファイル名"
   * hook/problem/result/cta ショットに適用
   */
  aiClips?: Record<string, string>;
  /** "auto" = hook/problem/result/ctaにAIクリップ、intro/demoはブラウザ録画 */
  blendMode?: "auto" | "browser-only";
};

/** auto blend モードでAIクリップを使うショットID */
const AI_BLEND_SHOT_IDS = new Set(["hook", "problem", "result", "cta"]);

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

  // アニメーションするグラジエントのアクセント位置
  const gradX = interpolate(frame, [0, durationInFrames], [35, 65], {
    extrapolateRight: "clamp",
  });
  const gradY = interpolate(frame, [0, durationInFrames], [25, 55], {
    extrapolateRight: "clamp",
  });
  const gradOpacity = interpolate(frame, [0, 20, durationInFrames - 10, durationInFrames], [0, 0.35, 0.35, 0], {
    extrapolateLeft: "clamp",
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
      {/* ゆっくり動くアクセントグラデーション（黒画面対策） */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at ${gradX}% ${gradY}%, rgba(74,172,255,${gradOpacity}) 0%, transparent 60%)`,
          pointerEvents: "none",
        }}
      />
      {/* 右下にも小さいアクセント */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at ${100 - gradX}% ${100 - gradY}%, rgba(138,43,226,${gradOpacity * 0.5}) 0%, transparent 50%)`,
          pointerEvents: "none",
        }}
      />
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

// ===== 上下固定フレームオーバーレイ =====

const FrameOverlay: React.FC<{ config: OverlayConfig }> = ({ config }) => {
  const {
    topHeight,
    bottomHeight,
    topColor,
    bottomColor,
    logoText,
    logoFontSize = 42,
    logoColor = "#FFFFFF",
    logoImage,
  } = config;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* 上帯: ロゴ画像スペース（画像がある場合のみ表示） */}
      {topHeight > 0 && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: topHeight,
            background: topColor,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            paddingLeft: 48,
            paddingRight: 48,
          }}
        >
          {logoImage && (
            <Img
              src={staticFile(logoImage)}
              style={{ height: topHeight * 0.52, objectFit: "contain" }}
            />
          )}
        </div>
      )}

      {/* 下部黒エリア: テロップ可読性のため常時表示 */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 420,
          background: "rgba(0,0,0,0.88)",
          pointerEvents: "none",
        }}
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

  const { shots, subtitles, style, files, actionsTimeline, aiClips, blendMode } = episode;
  const transitionDurationFrames = style.transition.durationFrames ?? 8;

  // ショットごとのフレーム尺を計算
  const shotDurations = shots.map((shot) => {
    const rawFrames = Math.round((shot.endSec - shot.startSec) * fps);
    // 最小1フレーム保証
    // トランジション長より短いショットはエラーになるため、最低 transitionDurationFrames+1 フレーム保証
    return Math.max(rawFrames, transitionDurationFrames + 1);
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
            // AIクリップが存在し、このショットがAIブレンド対象かチェック
            const aiClipSrc = aiClips?.[shot.id];
            const useAiClip =
              blendMode !== "browser-only" &&
              !!aiClipSrc &&
              AI_BLEND_SHOT_IDS.has(shot.id);

            if (useAiClip && aiClipSrc) {
              return (
                <AbsoluteFill>
                  <Video
                    src={staticFile(`project/${aiClipSrc}`)}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                </AbsoluteFill>
              );
            }

            if (shot.type === "video" && shot.src) {
              const videoStartSec = shot.videoStartSec ?? 0;
              const videoContent = (
                <VideoShot
                  src={staticFile(`project/${shot.src}`)}
                  startOffsetSec={videoStartSec}
                  durationInFrames={durationInFrames}
                />
              );
              // actionsTimeline がある場合はビデオをズームカメラでラップ
              if (actionsTimeline && actionsTimeline.length > 0) {
                return (
                  <AutoZoom
                    actionsTimeline={actionsTimeline}
                    videoStartSec={videoStartSec}
                  >
                    {videoContent}
                  </AutoZoom>
                );
              }
              return videoContent;
            }
            if (shot.type === "image" && shot.src) {
              return (
                <KenBurnsImage
                  src={staticFile(`project/${shot.src}`)}
                  durationInFrames={durationInFrames}
                />
              );
            }
            // type === "color"
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

      {/* 上下フレームオーバーレイ: 映像の上・テロップの下 */}
      {style.overlay && <FrameOverlay config={style.overlay} />}

      {/* テロップレイヤー: 映像の上に重ねる */}
      <CaptionOverlay subtitles={subtitles} telopStyle={telopStyle} />
    </AbsoluteFill>
  );
};
