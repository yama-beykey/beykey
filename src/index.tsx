import { Composition } from "remotion";
import { ShortVideo } from "./ShortVideo";

// デフォルト尺: 80秒 × 30fps = 2400フレーム（episode.jsonで上書き可能）
const DEFAULT_DURATION_FRAMES = 2400;

export const RemotionRoot = () => {
  return (
    <Composition
      id="ShortVideo"
      component={ShortVideo}
      durationInFrames={DEFAULT_DURATION_FRAMES}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};
