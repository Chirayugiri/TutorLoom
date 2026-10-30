import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import type {SceneProps} from '../types';

/** Shared chrome: background, section label, title, segmented progress bar, scene fade in/out. */
export const Frame: React.FC<SceneProps & {children: React.ReactNode; showTitle?: boolean}> = ({
	scene,
	theme,
	progress,
	children,
	showTitle = true,
}) => {
	const frame = useCurrentFrame();
	const c = theme.colors;
	const s = theme.sizes;
	const fade = theme.motion.fade_frames;
	const sceneOpacity = interpolate(
		frame,
		[0, fade, scene.duration_frames - fade, scene.duration_frames - 1],
		[0, 1, 1, 0],
		{extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
	);
	const titleIn = interpolate(frame, [3, 22], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	const [num, ...rest] = scene.section_label.split(' ');
	const hasNum = /^\d+$/.test(num ?? '');
	const labelText = hasNum ? rest.join(' ') : scene.section_label;

	return (
		<AbsoluteFill style={{backgroundColor: c.bg}}>
			<AbsoluteFill
				style={{
					background: `radial-gradient(ellipse 80% 70% at 50% 40%, ${c.bg_raised} 0%, ${c.bg} 70%)`,
				}}
			/>
			<AbsoluteFill style={{opacity: sceneOpacity}}>
				{scene.section_label ? (
					<div
						style={{
							position: 'absolute',
							left: s.margin_x,
							top: 58,
							display: 'flex',
							alignItems: 'baseline',
							gap: 14,
							opacity: titleIn,
						}}
					>
						{hasNum ? (
							<span style={{fontFamily: theme.fonts.serif, fontSize: 26, color: c.accent, fontWeight: 600}}>{num}</span>
						) : null}
						<span
							style={{
								fontFamily: theme.fonts.sans,
								fontSize: s.label,
								color: c.text_muted,
								letterSpacing: '0.14em',
								textTransform: 'uppercase',
								fontWeight: 500,
							}}
						>
							{labelText}
							{scene.subtitle ? <span style={{color: c.text_faint}}>{'  ·  '}{scene.subtitle}</span> : null}
						</span>
					</div>
				) : null}
				{showTitle ? (
					<div
						style={{
							position: 'absolute',
							left: s.margin_x,
							top: 104,
							fontFamily: theme.fonts.serif,
							fontSize: s.title,
							color: c.text,
							fontWeight: 400,
							letterSpacing: '-0.01em',
							opacity: titleIn,
							transform: `translateY(${(1 - titleIn) * 10}px)`,
						}}
					>
						{scene.title}
					</div>
				) : null}
				{children}
			</AbsoluteFill>
			<ProgressBar {...{scene, theme, progress}} />
		</AbsoluteFill>
	);
};

const ProgressBar: React.FC<SceneProps> = ({scene, theme, progress}) => {
	const frame = useCurrentFrame();
	const c = theme.colors;
	const left = theme.sizes.margin_x;
	const width = 1920 - 2 * left;
	const gap = 8;
	const total = progress.durations.reduce((a, b) => a + b, 0) || 1;
	const usable = width - gap * (progress.durations.length - 1);
	let x = left;
	return (
		<>
			{progress.durations.map((d, i) => {
				const w = (d / total) * usable;
				const seg = {x, w};
				x += w + gap;
				const fill = i < progress.index ? 1 : i > progress.index ? 0 : Math.min(1, frame / scene.duration_frames);
				const done = i < progress.index;
				return (
					<div key={i} style={{position: 'absolute', left: seg.x, top: 1032, width: seg.w, height: 3, borderRadius: 2, background: c.border}}>
						<div
							style={{
								width: `${fill * 100}%`,
								height: '100%',
								borderRadius: 2,
								background: done ? c.text_faint : c.accent,
							}}
						/>
					</div>
				);
			})}
		</>
	);
};
