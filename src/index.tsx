import { Composition, registerRoot, staticFile } from "remotion";
import { ShortVideo } from "./ShortVideo";

// episode.json の meta.durationSec からフレーム数を動的に計算
const calculateMetadata = async () => {
  const fps = 30;
  try {
    const res = await fetch(staticFile("project/episode.json"));
    const episode = await res.json();
    const durationSec: number = episode?.meta?.durationSec ?? 41;
    const durationInFrames = Math.ceil(durationSec * fps);
    return { durationInFrames, fps };
  } catch {
    // フォールバック: 41秒（38秒 + CTA3秒）
    return { durationInFrames: Math.ceil(41 * fps), fps };
  }
};

export const RemotionRoot = () => {
  return (
    <Composition
      id="ShortVideo"
      component={ShortVideo}
      durationInFrames={Math.ceil(41 * 30)}
      fps={30}
      width={1080}
      height={1920}
      calculateMetadata={calculateMetadata}
    />
  );
};

registerRoot(RemotionRoot);
