import React from 'react';
import {Frame} from '../components/Frame';
import type {SceneProps} from '../types';
import {CodeScene} from './CodeScene';
import {CompareCards} from './CompareCards';

const Placeholder: React.FC<SceneProps> = (props) => (
	<Frame {...props}>
		<div style={{position: 'absolute', left: 120, top: 300, color: props.theme.colors.text_faint, fontFamily: props.theme.fonts.mono, fontSize: 28}}>
			template "{props.scene.template}" not implemented yet
		</div>
	</Frame>
);

export const TEMPLATES: Record<string, React.FC<SceneProps>> = {
	compare_cards: CompareCards,
	code: CodeScene,
};

export const SceneRouter: React.FC<SceneProps> = (props) => {
	const C = TEMPLATES[props.scene.template] ?? Placeholder;
	return <C {...props} />;
};
