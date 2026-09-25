import {Composition} from 'remotion';
import {CaptionedVideo} from './CaptionedVideo';

// Set DURATION_SEC from ffprobe of public/source.mp4 after the cut is locked.
const FPS = 30;
const DURATION_SEC = 120;
const DURATION_IN_FRAMES = Math.round(DURATION_SEC * FPS);

export const MyComposition = () => {
  return (
    <Composition
      id="LinkedInVertical"
      component={CaptionedVideo}
      durationInFrames={DURATION_IN_FRAMES}
      fps={FPS}
      width={1080}
      height={1920}
    />
  );
};
