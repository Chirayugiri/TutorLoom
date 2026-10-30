import React from 'react';
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Frame} from '../components/Frame';
import {BeatState, mix} from '../lib/beats';
import {DEFAULT_Y, DISCONTINUITIES, FNS, type FnName} from '../lib/functions';
import type {SceneProps, Theme} from '../types';

type Card = {
	name: string;
	label: string;
	fn: FnName;
	symbol?: string;
	formula_html?: string;
	caption?: string;
	y_range?: [number, number];
};

const PLOT_W = 340;
// toFixed without the "-0.0" artefact
const fmt = (v: number, d: number) => (Math.abs(v) < 0.5 * 10 ** -d ? 0 : v).toFixed(d);
const PLOT_H = 330;

export const CompareCards: React.FC<SceneProps> = (props) => {
	const {scene, theme} = props;
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const st = new BeatState(scene.beats, frame, fps, theme);
	const cards: Card[] = scene.content.cards ?? [];
	const xRange: [number, number] = scene.content.x_range ?? [-4, 4];
	const n = cards.length;
	const gap = 32;
	const left = theme.sizes.margin_x;
	const cardW = (1920 - 2 * left - gap * (n - 1)) / n;

	const cardFocus = (name: string) =>
		Math.max(st.focus(`card:${name}`), st.focus(`formula:${name}`), st.focus(`plot:${name}`), st.focus(`dot:${name}`));
	const groupFocus = Math.max(0, ...cards.map((c) => cardFocus(c.name)));

	return (
		<Frame {...props}>
			{cards.map((card, i) => {
				const f = cardFocus(card.name);
				const vis = st.reveal(`card:${card.name}`, 14 + i * 5);
				const opacity = vis * st.dim(f, groupFocus);
				return (
					<div
						key={card.name}
						style={{
							position: 'absolute',
							left: left + i * (cardW + gap),
							top: 268,
							width: cardW,
							height: 720,
							boxSizing: 'border-box',
							borderRadius: theme.sizes.radius,
							border: `${theme.sizes.border}px solid ${mix(theme.colors.border, theme.colors.accent, f)}`,
							background: theme.colors.card,
							boxShadow: `0 24px 80px rgba(255, 176, 0, ${0.07 * f})`,
							opacity,
							transform: `translateY(${(1 - vis) * 18 - 6 * f}px) scale(${1 + (theme.motion.focus_scale - 1) * f})`,
							padding: '36px 30px 28px',
							display: 'flex',
							flexDirection: 'column',
						}}
					>
						<div style={{display: 'flex', alignItems: 'center', gap: 12}}>
							<div
								style={{
									width: 9,
									height: 9,
									borderRadius: 5,
									background: theme.colors.accent,
									opacity: f,
									transform: `scale(${0.4 + 0.6 * f})`,
								}}
							/>
							<div style={{fontFamily: theme.fonts.serif, fontSize: 42, color: theme.colors.text, marginLeft: -21 + 21 * f}}>
								{card.label}
							</div>
						</div>
						<div
							style={{
								height: 112,
								display: 'flex',
								alignItems: 'center',
								fontSize: 25,
								color: mix(theme.colors.text_muted, theme.colors.accent, st.focus(`formula:${card.name}`)),
							}}
							dangerouslySetInnerHTML={{__html: card.formula_html ?? ''}}
						/>
						<Plot card={card} xRange={xRange} st={st} theme={theme} focus={f} index={i} frame={frame} />
						<div style={{flex: 1}} />
						<div
							style={{
								fontFamily: theme.fonts.sans,
								fontSize: theme.sizes.label,
								color: theme.colors.text_muted,
								borderTop: `1px solid ${theme.colors.border}`,
								paddingTop: 18,
								letterSpacing: '0.02em',
							}}
						>
							{card.caption}
						</div>
					</div>
				);
			})}
		</Frame>
	);
};

const Plot: React.FC<{
	card: Card;
	xRange: [number, number];
	st: BeatState;
	theme: Theme;
	focus: number;
	index: number;
	frame: number;
}> = ({card, xRange, st, theme, focus, index, frame}) => {
	const fn = FNS[card.fn] ?? FNS.identity;
	const [y0, y1] = card.y_range ?? DEFAULT_Y[card.fn] ?? [-1.5, 1.5];
	const [x0, x1] = xRange;
	const pad = 8;
	const sx = (x: number) => pad + ((x - x0) / (x1 - x0)) * (PLOT_W - 2 * pad);
	const sy = (y: number) => PLOT_H - pad - ((y - y0) / (y1 - y0)) * (PLOT_H - 2 * pad);

	// Sample the curve, splitting at discontinuities.
	const breaks = DISCONTINUITIES[card.fn] ?? [];
	const segments: [number, number][][] = [[]];
	const N = 240;
	for (let k = 0; k <= N; k++) {
		const x = x0 + ((x1 - x0) * k) / N;
		const prev = x0 + ((x1 - x0) * (k - 1)) / N;
		if (k > 0 && breaks.some((b) => prev < b && x >= b)) {
			segments[segments.length - 1].push([sx(breaks[0] - 1e-9), sy(fn(breaks[0] - 1e-9))]);
			segments.push([[sx(breaks[0]), sy(fn(breaks[0]))]]);
		}
		segments[segments.length - 1].push([sx(x), sy(fn(x))]);
	}
	const lengths = segments.map((seg) => seg.reduce((acc, p, k) => (k ? acc + Math.hypot(p[0] - seg[k - 1][0], p[1] - seg[k - 1][1]) : 0), 0));
	const total = lengths.reduce((a, b) => a + b, 0);

	// Draw progress: an explicit `draw` beat, otherwise a staggered line-draw at scene start.
	const target = `plot:${card.name}`;
	const draw = st.hasReveal(target)
		? st.progress(target, 'draw').t
		: interpolate(frame, [24 + index * 7, 64 + index * 7], [0, 1], {
				extrapolateLeft: 'clamp',
				extrapolateRight: 'clamp',
				easing: Easing.inOut(Easing.cubic),
			});
	let remaining = draw * total;
	const curveColor = mix('rgba(242, 240, 235, 0.88)', theme.colors.accent, focus);

	// Moving dot
	const dotTarget = `dot:${card.name}`;
	const dotFocus = st.focus(dotTarget, ['move_dot', 'highlight']);
	const {t: dotT, beat: dotBeat} = st.progress(dotTarget, 'move_dot');
	const from = Number(dotBeat?.params?.from ?? x0 + 0.6);
	const to = Number(dotBeat?.params?.to ?? x1 - 0.6);
	const dx = from + (to - from) * dotT;
	const dy = fn(dx);
	const sym = card.symbol ?? 'f';

	const axis = theme.colors.border_strong;
	const grid = theme.colors.grid;
	const tickYs = [-1, 1, 2, 3].filter((v) => v > y0 && v < y1);

	return (
		<svg width={PLOT_W} height={PLOT_H} style={{overflow: 'visible', marginTop: 8}}>
			{tickYs.map((v) => (
				<g key={v}>
					<line x1={sx(x0)} x2={sx(x1)} y1={sy(v)} y2={sy(v)} stroke={grid} strokeWidth={1.2} strokeDasharray="3 6" />
					<text x={sx(x0) - 6} y={sy(v) + 5} fill={theme.colors.text_faint} fontSize={15} fontFamily={theme.fonts.mono} textAnchor="end">
						{v}
					</text>
				</g>
			))}
			<line x1={sx(x0)} x2={sx(x1)} y1={sy(0)} y2={sy(0)} stroke={axis} strokeWidth={1.4} />
			<line x1={sx(0)} x2={sx(0)} y1={sy(y0)} y2={sy(y1)} stroke={axis} strokeWidth={1.4} />
			{segments.map((seg, k) => {
				const len = lengths[k];
				const shown = Math.max(0, Math.min(len, remaining));
				remaining -= len;
				return (
					<path
						key={k}
						d={seg.map((p, j) => `${j ? 'L' : 'M'}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(' ')}
						fill="none"
						stroke={curveColor}
						strokeWidth={3.2}
						strokeLinecap="round"
						strokeLinejoin="round"
						strokeDasharray={`${len} ${len + 1}`}
						strokeDashoffset={len - shown}
					/>
				);
			})}
			{dotFocus > 0.001 ? (
				<g opacity={dotFocus}>
					<line x1={sx(dx)} x2={sx(dx)} y1={sy(0)} y2={sy(dy)} stroke={theme.colors.accent} strokeWidth={1.4} strokeDasharray="4 5" opacity={0.7} />
					<circle cx={sx(dx)} cy={sy(dy)} r={15} fill={theme.colors.accent} opacity={0.16} />
					<circle cx={sx(dx)} cy={sy(dy)} r={7.5} fill={theme.colors.accent} />
					<text
						x={Math.min(PLOT_W - 4, Math.max(4, sx(dx)))}
						y={Math.max(16, sy(dy) - 24)}
						fill={theme.colors.accent}
						fontSize={19}
						fontFamily={theme.fonts.mono}
						textAnchor={sx(dx) > PLOT_W * 0.6 ? 'end' : sx(dx) < PLOT_W * 0.3 ? 'start' : 'middle'}
						stroke={theme.colors.card}
						strokeWidth={8}
						strokeLinejoin="round"
						paintOrder="stroke"
					>
						{`${sym}(${fmt(dx, 1)}) = ${fmt(dy, 2)}`}
					</text>
				</g>
			) : null}
		</svg>
	);
};
