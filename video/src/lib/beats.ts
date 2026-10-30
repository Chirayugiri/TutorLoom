import {interpolate, spring, Easing} from 'remotion';
import type {ResolvedBeat, Theme, Action} from '../types';

const FOCUS: Action[] = ['highlight', 'circle', 'box', 'zoom', 'dim_others', 'move_dot'];
const OUT_FRAMES = 9;

/**
 * Time-driven state for every targetable element in a scene. All animation is a pure
 * function of the frame and the resolved beats — no guessed timestamps anywhere.
 */
export class BeatState {
	constructor(
		private beats: ResolvedBeat[],
		private frame: number,
		private fps: number,
		private theme: Theme,
	) {}

	private ease(b: ResolvedBeat): number {
		const f = this.frame - b.start_frame;
		if (f < 0) return 0;
		const {damping, stiffness, mass} = this.theme.motion;
		const inn = spring({frame: f, fps: this.fps, config: {damping, stiffness, mass}, durationInFrames: b.in_frames});
		return inn;
	}

	private focusOf(b: ResolvedBeat): number {
		const inn = this.ease(b);
		const out = interpolate(this.frame, [b.end_frame, b.end_frame + OUT_FRAMES], [1, 0], {
			extrapolateLeft: 'clamp',
			extrapolateRight: 'clamp',
			easing: Easing.inOut(Easing.cubic),
		});
		return inn * out;
	}

	/** 0..1 focus on a target, optionally limited to some actions. */
	focus(target: string, actions: Action[] = FOCUS): number {
		let v = 0;
		for (const b of this.beats) {
			if (b.target === target && actions.includes(b.action)) v = Math.max(v, this.focusOf(b));
		}
		return v;
	}

	/** Max focus over all targets matching a predicate — used to dim the non-focused siblings. */
	focusWhere(pred: (target: string) => boolean, actions: Action[] = FOCUS): number {
		let v = 0;
		for (const b of this.beats) {
			if (pred(b.target) && actions.includes(b.action)) v = Math.max(v, this.focusOf(b));
		}
		return v;
	}

	/** Has this target got reveal/draw beats? If so it is hidden until the first one fires. */
	hasReveal(target: string): boolean {
		return this.beats.some((b) => b.target === target && (b.action === 'reveal' || b.action === 'draw'));
	}

	/** 0..1 visibility. Elements without reveal beats use `introFrame` as a gentle scene-start entrance. */
	reveal(target: string, introFrame = 8): number {
		const rs = this.beats.filter((b) => b.target === target && (b.action === 'reveal' || b.action === 'draw'));
		if (rs.length === 0) {
			return interpolate(this.frame, [introFrame, introFrame + 16], [0, 1], {
				extrapolateLeft: 'clamp',
				extrapolateRight: 'clamp',
				easing: Easing.out(Easing.cubic),
			});
		}
		return Math.max(...rs.map((b) => this.ease(b)));
	}

	/** Linear 0..1 progress through a beat's in-window (eased in-out), for draws and moving dots. */
	progress(target: string, action: Action): {t: number; beat: ResolvedBeat | null} {
		let best: ResolvedBeat | null = null;
		for (const b of this.beats) {
			if (b.target === target && b.action === action && b.start_frame <= this.frame) best = b;
		}
		if (!best) return {t: 0, beat: null};
		const t = interpolate(this.frame, [best.start_frame, best.start_frame + best.in_frames], [0, 1], {
			extrapolateLeft: 'clamp',
			extrapolateRight: 'clamp',
			easing: Easing.inOut(Easing.cubic),
		});
		return {t, beat: best};
	}

	/** Opacity for a sibling: dims when something else in its group is focused. */
	dim(selfFocus: number, groupFocus: number): number {
		const d = this.theme.motion.dim_opacity;
		const others = Math.max(0, groupFocus - selfFocus);
		return interpolate(others, [0, 1], [1, d]);
	}
}

export const mix = (a: string, b: string, t: number): string => {
	const pa = parse(a);
	const pb = parse(b);
	const c = pa.map((v, i) => v + (pb[i] - v) * t);
	return `rgba(${Math.round(c[0])}, ${Math.round(c[1])}, ${Math.round(c[2])}, ${c[3].toFixed(3)})`;
};

const parse = (c: string): number[] => {
	if (c.startsWith('#')) {
		const h = c.slice(1);
		return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 1];
	}
	const m = c.match(/[\d.]+/g)!.map(Number);
	return [m[0], m[1], m[2], m[3] ?? 1];
};
