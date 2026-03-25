import { Composition, registerRoot } from "remotion";
import { ShortVideo } from "./ShortVideo";

// デフォルト尺: 3分 × 30fps = 5400フレーム（最大3分の動画に対応）
const DEFAULT_DURATION_FRAMES = 5400;

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

registerRoot(RemotionRoot);
