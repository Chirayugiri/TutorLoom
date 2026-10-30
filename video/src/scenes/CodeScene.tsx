import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {Frame} from '../components/Frame';
import {BeatState, mix} from '../lib/beats';
import type {CodeToken, SceneProps, Theme} from '../types';

const TOP = 236;
const LEFT_W = 1010;
const COL_GAP = 40;
const BOTTOM = 990;

type Chart = {
	title?: string;
	labels: string[];
	series: {name: string; values: number[]}[];
	caption?: string;
};

export const CodeScene: React.FC<SceneProps> = (props) => {
	const {scene, theme} = props;
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const st = new BeatState(scene.beats, frame, fps, theme);
	const c = theme.colors;
	const left = theme.sizes.margin_x;
	const fontSize = theme.sizes.code;
	const lineH = Math.round(fontSize * 1.58);
	const charW = fontSize * 0.6; // JetBrains Mono advance width is exactly 0.6em
	const tokens: CodeToken[][] = scene.content.tokens ?? [];
	const outLines: string[] = (scene.content.output ?? '').replace(/\n$/, '').split('\n');
	const chart: Chart | undefined = scene.content.chart;

	const codePadX = 30;
	const gutter = 46;
	const codeH = 64 + tokens.length * lineH + 26;
	const outFont = fontSize * 0.86;
	const outLineH = Math.round(outFont * 1.6);
	const outH = 60 + outLines.length * outLineH + 22;
	const rightX = left + LEFT_W + COL_GAP;
	const rightW = 1920 - 2 * left - LEFT_W - COL_GAP;
	// With a chart, the printed output sits above it on the right; without one, below the code.
	const outBox = chart ? {x: rightX, y: TOP, w: rightW} : {x: left, y: TOP + codeH + 24, w: LEFT_W};

	const codeFocus = st.focusWhere((t) => t.startsWith('line:') || t.startsWith('token:'));
	const outFocus = st.focusWhere((t) => t.startsWith('output:'));
	const panelVis = (p: string, intro: number) => st.reveal(`panel:${p}`, intro);

	// Token boxes: first occurrence (or params.line) of each targeted token.
	const tokenBeats = scene.beats.filter((b) => b.target.startsWith('token:'));
	const tokenPos = (text: string, lineHint?: number) => {
		for (let li = 0; li < tokens.length; li++) {
			if (lineHint && li + 1 !== lineHint) continue;
			const lineText = tokens[li].map((t) => t.content).join('');
			const re = new RegExp(`(?<![A-Za-z0-9_.])${text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![A-Za-z0-9_])`);
			const m = re.exec(lineText);
			if (m) return {line: li, col: m.index, len: text.length};
		}
		return null;
	};

	return (
		<Frame {...props}>
			{/* ---------------- code card */}
			<Card theme={theme} x={left} y={TOP} w={LEFT_W} h={codeH} vis={panelVis('code', 12)} focus={st.focus('panel:code')}>
				<PanelLabel theme={theme} text={scene.content.filename ?? scene.content.language ?? 'code'} />
				<div style={{position: 'absolute', left: 0, top: 64, width: '100%'}}>
					{tokens.map((line, i) => {
						const tgt = `line:${i + 1}`;
						const f = st.focus(tgt);
						const boxF = st.focus(tgt, ['box']);
						const vis = st.hasReveal(tgt) ? st.reveal(tgt) : 1;
						const tokenOnLine = tokenBeats.some((b) => tokenPos(b.target.slice(6), Number(b.params?.line) || undefined)?.line === i && st.focus(b.target) > 0.01);
						const dimmed = st.dim(Math.max(f, tokenOnLine ? 1 : 0), codeFocus);
						return (
							<div key={i} style={{position: 'absolute', top: i * lineH, left: 0, width: '100%', height: lineH, opacity: vis}}>
								<div
									style={{
										position: 'absolute',
										left: 10,
										right: 10,
										top: 2,
										bottom: 2,
										borderRadius: 8,
										background: c.accent_soft,
										opacity: f,
										border: boxF > 0 ? `1.5px solid ${mix('rgba(255,176,0,0)', c.accent, boxF)}` : undefined,
									}}
								/>
								<div style={{position: 'absolute', left: 10, top: 6, bottom: 6, width: 3, borderRadius: 2, background: c.accent, opacity: f}} />
								<div
									style={{
										position: 'absolute',
										left: codePadX,
										width: gutter - 14,
										textAlign: 'right',
										top: 0,
										lineHeight: `${lineH}px`,
										fontFamily: theme.fonts.mono,
										fontSize: fontSize * 0.72,
										color: mix(c.text_faint, c.accent, f),
										opacity: dimmed,
									}}
								>
									{i + 1}
								</div>
								<div
									style={{
										position: 'absolute',
										left: codePadX + gutter,
										top: 0,
										whiteSpace: 'pre',
										fontFamily: theme.fonts.mono,
										fontSize,
										lineHeight: `${lineH}px`,
										opacity: dimmed,
										transform: `translateX(${(1 - vis) * -12}px)`,
									}}
								>
									{line.map((t, k) => (
										<span key={k} style={{color: t.color, fontStyle: t.italic ? 'italic' : 'normal'}}>
											{t.content}
										</span>
									))}
								</div>
							</div>
						);
					})}
					{tokenBeats.map((b, k) => {
						const pos = tokenPos(b.target.slice(6), Number(b.params?.line) || undefined);
						if (!pos) return null;
						const f = st.focus(b.target);
						if (f < 0.001) return null;
						const circle = b.action === 'circle';
						const x = codePadX + gutter + pos.col * charW;
						const w = pos.len * charW;
						return (
							<div
								key={k}
								style={{
									position: 'absolute',
									left: x - (circle ? 16 : 7),
									top: pos.line * lineH + (circle ? -4 : 3),
									width: w + (circle ? 32 : 14),
									height: lineH - (circle ? -8 : 6),
									borderRadius: circle ? '50%' : 7,
									border: `2px solid ${c.accent}`,
									background: circle ? 'transparent' : 'rgba(255,176,0,0.10)',
									opacity: f,
									transform: `scale(${1.15 - 0.15 * f})`,
								}}
							/>
						);
					})}
				</div>
			</Card>

			{/* ---------------- printed output */}
			<Card
				theme={theme}
				x={outBox.x}
				y={outBox.y}
				w={outBox.w}
				h={Math.min(BOTTOM - outBox.y, outH)}
				vis={panelVis('output', 30)}
				focus={st.focus('panel:output')}
			>
				<PanelLabel theme={theme} text="printed output" />
				{outLines.map((line, i) => {
					const f = st.focus(`output:${i + 1}`);
					return (
						<div
							key={i}
							style={{
								position: 'absolute',
								left: 12,
								right: 12,
								top: 60 + i * outLineH,
								height: outLineH,
								borderRadius: 8,
								background: `rgba(255,176,0,${0.12 * f})`,
							}}
						>
							<div
								style={{
									paddingLeft: codePadX - 12,
									whiteSpace: 'pre',
									fontFamily: theme.fonts.mono,
									fontSize: outFont,
									lineHeight: `${outLineH}px`,
									color: mix(c.text, c.accent, f),
									opacity: st.dim(f, outFocus),
								}}
							>
								{line}
							</div>
						</div>
					);
				})}
			</Card>

			{/* ---------------- chart */}
			{chart ? (
				<BarChart
					chart={chart}
					st={st}
					theme={theme}
					x={rightX}
					y={TOP + outH + 24}
					w={rightW}
					h={BOTTOM - TOP - outH - 24}
					frame={frame}
				/>
			) : null}
		</Frame>
	);
};

const Card: React.FC<{theme: Theme; x: number; y: number; w: number; h: number; vis: number; focus: number; children: React.ReactNode}> = ({
	theme,
	x,
	y,
	w,
	h,
	vis,
	focus,
	children,
}) => (
	<div
		style={{
			position: 'absolute',
			left: x,
			top: y,
			width: w,
			height: h,
			boxSizing: 'border-box',
			borderRadius: theme.sizes.radius,
			border: `${theme.sizes.border}px solid ${mix(theme.colors.border, theme.colors.accent, focus)}`,
			background: theme.colors.card,
			opacity: vis,
			transform: `translateY(${(1 - vis) * 16}px)`,
			overflow: 'hidden',
		}}
	>
		{children}
	</div>
);

const PanelLabel: React.FC<{theme: Theme; text: string}> = ({theme, text}) => (
	<div
		style={{
			position: 'absolute',
			left: 30,
			top: 22,
			fontFamily: theme.fonts.sans,
			fontSize: 16,
			fontWeight: 600,
			letterSpacing: '0.16em',
			textTransform: 'uppercase',
			color: theme.colors.text_faint,
		}}
	>
		{text}
	</div>
);

const BarChart: React.FC<{chart: Chart; st: BeatState; theme: Theme; x: number; y: number; w: number; h: number; frame: number}> = ({
	chart,
	st,
	theme,
	x,
	y,
	w,
	h,
}) => {
	const c = theme.colors;
	const vis = st.reveal('panel:chart', 40);
	const all = chart.series.flatMap((s) => s.values);
	const lo = Math.min(0, ...all);
	const hi = Math.max(0, ...all);
	const span = hi - lo || 1;
	const padL = 36;
	const padR = 30;
	const plotTop = 140;
	const plotBottom = h - (chart.caption ? 112 : 84);
	const plotH = plotBottom - plotTop;
	const sy = (v: number) => plotTop + ((hi + span * 0.12 - v) / (span * 1.12)) * plotH;
	const nG = chart.labels.length;
	const nS = chart.series.length;
	const groupW = (w - padL - padR) / nG;
	const barGap = 6;
	const barW = Math.min(46, (groupW * 0.72 - barGap * (nS - 1)) / nS);
	const seriesBase = [c.text, c.text_muted, c.text_faint];

	const groupFocus = st.focusWhere((t) => t.startsWith('bar:'));
	const seriesFocus = st.focusWhere((t) => t.startsWith('series:'));

	return (
		<div
			style={{
				position: 'absolute',
				left: x,
				top: y,
				width: w,
				height: h,
				boxSizing: 'border-box',
				borderRadius: theme.sizes.radius,
				border: `${theme.sizes.border}px solid ${mix(c.border, c.accent, st.focus('panel:chart'))}`,
				background: c.card,
				opacity: vis,
				transform: `translateY(${(1 - vis) * 16}px)`,
			}}
		>
			<PanelLabel theme={theme} text={chart.title ?? 'result'} />
			<div style={{position: 'absolute', left: 30, top: 62, display: 'flex', gap: 26}}>
				{chart.series.map((s, k) => {
					const f = st.focus(`series:${s.name}`);
					return (
						<div key={s.name} style={{display: 'flex', alignItems: 'center', gap: 10, opacity: st.dim(f, seriesFocus)}}>
							<div style={{width: 14, height: 14, borderRadius: 3, background: mix(seriesBase[k % 3], c.accent, f)}} />
							<span style={{fontFamily: theme.fonts.sans, fontSize: 20, color: mix(c.text_muted, c.accent, f)}}>{s.name}</span>
						</div>
					);
				})}
			</div>
			<svg width={w} height={h} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
				<line x1={padL - 10} x2={w - padR + 10} y1={sy(0)} y2={sy(0)} stroke={c.border_strong} strokeWidth={1.5} />
				{chart.labels.map((label, g) => {
					const gf = st.focus(`bar:${label}`);
					const gx = padL + g * groupW + (groupW - (nS * barW + (nS - 1) * barGap)) / 2;
					const grow = st.hasReveal(`bar:${label}`) ? st.reveal(`bar:${label}`) : Math.min(1, Math.max(0, vis * 1.6 - g * 0.12));
					return (
						<g key={label} opacity={st.dim(gf, groupFocus)}>
							{gf > 0.001 ? (
								<rect
									x={padL + g * groupW + 4}
									y={plotTop - 18}
									width={groupW - 8}
									height={plotH + 76}
									rx={10}
									fill={`rgba(255,176,0,${0.07 * gf})`}
								/>
							) : null}
							{chart.series.map((s, k) => {
								const v = s.values[g] ?? 0;
								const sf = st.focus(`series:${s.name}`);
								const f = Math.max(gf, sf);
								const top = sy(Math.max(0, v * grow));
								const bottom = sy(Math.min(0, v * grow));
								const bx = gx + k * (barW + barGap);
								return (
									<g key={s.name} opacity={st.dim(sf, seriesFocus)}>
										<rect x={bx} y={top} width={barW} height={Math.max(0, bottom - top)} rx={4} fill={mix(seriesBase[k % 3], c.accent, f)} />
										<text
											x={bx + barW / 2}
											y={v >= 0 ? top - 10 : bottom + 22}
											fill={mix(c.text_muted, c.accent, f)}
											fontSize={15}
											fontFamily={theme.fonts.mono}
											textAnchor="middle"
											opacity={grow}
										>
											{v.toFixed(2)}
										</text>
									</g>
								);
							})}
							<text
								x={padL + g * groupW + groupW / 2}
								y={plotBottom + 50}
								fill={mix(c.text_muted, c.accent, gf)}
								fontSize={19}
								fontFamily={theme.fonts.mono}
								textAnchor="middle"
							>
								{label}
							</text>
						</g>
					);
				})}
			</svg>
			{chart.caption ? (
				<div
					style={{
						position: 'absolute',
						left: 30,
						right: 30,
						bottom: 24,
						fontFamily: theme.fonts.sans,
						fontSize: 18,
						color: c.text_faint,
						textAlign: 'center',
					}}
				>
					{chart.caption}
				</div>
			) : null}
		</div>
	);
};
