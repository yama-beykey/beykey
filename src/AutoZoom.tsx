/**
 * AutoZoom.tsx
 * Remotion カメラ追跡ズームコンポーネント
 *
 * actions_timeline.json の各アクションポイントに従い、
 * スムーズなズームイン／パンを useCurrentFrame + interpolate で実現する。
 *
 * 座標系: 動画の左上を (0, 0) とした 1080×1920 ピクセル空間
 * 変換式: translate(cx, cy) scale(s) translate(-focusX, -focusY)
 *   → focusX/Y が画面中央 (540, 960) に来るようにズーム
 */
import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type ActionPoint = {
  /** 録画開始からの秒数 */
  t: number;
  type: "navigate" | "scroll" | "highlight" | "click";
  /** ズームの焦点X (0〜1080) */
  focusX: number;
  /** ズームの焦点Y (0〜1920) */
  focusY: number;
  /** ズーム倍率 (1.0 = 等倍, 1.4 = 40%拡大) */
  scale: number;
};

/**
 * AutoZoom
 * actionsTimeline が空または未指定の場合はそのまま children を描画する。
 */
export const AutoZoom: React.FC<{
  actionsTimeline: ActionPoint[];
  /** ビデオ再生の開始オフセット（Sequence内のframe=0が録画のvideStartSec秒に対応する場合に指定） */
  videoStartSec?: number;
  children: React.ReactNode;
}> = ({ actionsTimeline, videoStartSec = 0, children }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  if (!actionsTimeline || actionsTimeline.length === 0) {
    return <AbsoluteFill>{children}</AbsoluteFill>;
  }

  // 現在の録画時刻 (videoStartSec でオフセット)
  const currentRecordingSec = frame / fps + videoStartSec;

  // アクションポイントを時刻順にソート
  const sorted = [...actionsTimeline].sort((a, b) => a.t - b.t);

  // 録画開始前に全画面表示の初期ポイントを補完
  const points: ActionPoint[] =
    sorted[0].t > 0
      ? [
          {
            t: 0,
            type: "navigate",
            focusX: width / 2,
            focusY: height / 2,
            scale: 1.0,
          },
          ...sorted,
        ]
      : sorted;

  // interpolate 用: フレーム値に変換（ここでは秒→秒のまま扱う）
  const tValues = points.map((p) => p.t);
  const fxValues = points.map((p) => p.focusX);
  const fyValues = points.map((p) => p.focusY);
  const scaleValues = points.map((p) => p.scale);

  const easing = Easing.inOut(Easing.ease);
  const opts = {
    extrapolateLeft: "clamp" as const,
    extrapolateRight: "clamp" as const,
    easing,
  };

  const currentScale = interpolate(currentRecordingSec, tValues, scaleValues, opts);
  const currentFocusX = interpolate(currentRecordingSec, tValues, fxValues, opts);
  const currentFocusY = interpolate(currentRecordingSec, tValues, fyValues, opts);

  // 変換: translate(cx,cy) scale(s) translate(-focusX,-focusY)
  // → focusX/Y が画面中央 (cx, cy) に来る
  const cx = width / 2;
  const cy = height / 2;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `translate(${cx}px, ${cy}px) scale(${currentScale}) translate(${-currentFocusX}px, ${-currentFocusY}px)`,
          transformOrigin: "0 0",
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
