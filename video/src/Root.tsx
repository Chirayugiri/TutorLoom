import 'katex/dist/katex.min.css';
import './fonts';
import React from 'react';
import {Composition} from 'remotion';
import {SceneRouter} from './scenes';
import type {SceneProps} from './types';
import sample from './sample-props.json';

export const RemotionRoot: React.FC = () => (
	<Composition
		id="Scene"
		component={SceneRouter}
		width={1920}
		height={1080}
		fps={30}
		durationInFrames={300}
		defaultProps={sample as unknown as SceneProps}
		calculateMetadata={({props}) => ({durationInFrames: props.scene.duration_frames})}
	/>
);
