import {useCallback, useEffect, useMemo, useState} from 'react';
import {
  AbsoluteFill,
  Composition,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useDelayRender,
  useVideoConfig,
} from 'remotion';
import {createTikTokStyleCaptions} from '@remotion/captions';
import type {Caption, TikTokPage} from '@remotion/captions';

// Set DURATION_SEC from ffprobe of public/source.mp4 after the cut is locked.
const FPS = 30;
const DURATION_SEC = 120;
const DURATION_IN_FRAMES = Math.round(DURATION_SEC * FPS);

// Crop: left speaker stack on a 1280x720 source into 1080x1920. Edit if your source differs.
const SOURCE_WIDTH = 1280;
const SOURCE_HEIGHT = 720;
const CROP_X = 0;

const SWITCH_CAPTIONS_EVERY_MS = 0;
const HIGHLIGHT = '#39E508';
const FADE_OUT_SEC = 0.5;

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

const CaptionedVideo: React.FC = () => {
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const {delayRender, continueRender, cancelRender} = useDelayRender();
  const [handle] = useState(() => delayRender('captions'));
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const fadeFrames = Math.max(1, Math.round(FADE_OUT_SEC * fps));
  const opacity = interpolate(
    frame,
    [durationInFrames - fadeFrames, durationInFrames - 1],
    [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );

  const fetchCaptions = useCallback(async () => {
    try {
      const response = await fetch(staticFile('captions.json'));
      const data = (await response.json()) as Caption[];
      setCaptions(data);
      continueRender(handle);
    } catch (e) {
      cancelRender(e);
    }
  }, [cancelRender, continueRender, handle]);

  useEffect(() => {
    fetchCaptions();
  }, [fetchCaptions]);

  if (!captions) {
    return null;
  }

  return (
    <AbsoluteFill style={{backgroundColor: '#000', opacity}}>
      <SpeakerCropVideo fadeFrames={fadeFrames} />
      <OneWordCaptions captions={captions} />
    </AbsoluteFill>
  );
};

const SpeakerCropVideo: React.FC<{fadeFrames: number}> = ({fadeFrames}) => {
  const scale = 1920 / SOURCE_HEIGHT;
  const scaledWidth = SOURCE_WIDTH * scale;
  const {durationInFrames} = useVideoConfig();

  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <OffthreadVideo
        src={staticFile('source.mp4')}
        volume={(f) =>
          interpolate(
            f,
            [durationInFrames - fadeFrames, durationInFrames - 1],
            [1, 0],
            {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
          )
        }
        style={{
          position: 'absolute',
          height: 1920,
          width: scaledWidth,
          left: -CROP_X * scale,
          top: 0,
          maxWidth: 'none',
        }}
      />
    </AbsoluteFill>
  );
};

const OneWordCaptions: React.FC<{captions: Caption[]}> = ({captions}) => {
  const {fps} = useVideoConfig();

  const {pages} = useMemo(() => {
    return createTikTokStyleCaptions({
      captions,
      combineTokensWithinMilliseconds: SWITCH_CAPTIONS_EVERY_MS,
    });
  }, [captions]);

  return (
    <AbsoluteFill>
      {pages.map((page, index) => {
        const nextPage = pages[index + 1] ?? null;
        const startFrame = Math.round((page.startMs / 1000) * fps);
        const endFrame = nextPage
          ? Math.round((nextPage.startMs / 1000) * fps)
          : startFrame +
            Math.max(
              1,
              Math.round(((page.tokens[0]?.toMs ?? page.startMs + 300) - page.startMs) / 1000) * fps,
            );
        const durationInFrames = Math.max(1, endFrame - startFrame);

        return (
          <Sequence key={`${page.startMs}-${index}`} from={startFrame} durationInFrames={durationInFrames}>
            <CaptionWord page={page} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const CaptionWord: React.FC<{page: TikTokPage}> = ({page}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const currentTimeMs = (frame / fps) * 1000;
  const absoluteTimeMs = page.startMs + currentTimeMs;
  const word = page.tokens.map((t) => t.text).join('').trim();
  if (!word) {
    return null;
  }

  const isActive = page.tokens.some(
    (token) => token.fromMs <= absoluteTimeMs && token.toMs > absoluteTimeMs,
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        // Low on bottom cam — clears faces; sits above lower-third name tags. Nudge if needed.
        paddingBottom: '9%',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          fontSize: 84,
          fontWeight: 900,
          fontFamily: 'Arial Black, Helvetica Neue, Arial, sans-serif',
          textTransform: 'uppercase',
          letterSpacing: 1,
          color: isActive ? HIGHLIGHT : '#fff',
          textAlign: 'center',
          whiteSpace: 'pre',
          textShadow:
            '0 0 8px rgba(0,0,0,0.85), 3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000',
          maxWidth: '88%',
          lineHeight: 1.05,
        }}
      >
        {word}
      </div>
    </AbsoluteFill>
  );
};
