// Mirrors notes2video/schemas.py (Timeline*) — keep in sync.

export type Action = 'highlight' | 'reveal' | 'circle' | 'box' | 'zoom' | 'dim_others' | 'draw' | 'move_dot';

export type ResolvedBeat = {
	action: Action;
	target: string;
	anchor: string;
	start_frame: number;
	end_frame: number;
	in_frames: number;
	params: Record<string, unknown>;
};

export type TimedWord = {text: string; start: number; end: number};

export type TimelineScene = {
	id: string;
	template: string;
	section_label: string;
	subtitle: string;
	title: string;
	content: Record<string, any>;
	beats: ResolvedBeat[];
	duration_frames: number;
	audio_offset_frames: number;
	audio_file: string;
	words: TimedWord[];
};

export type Theme = {
	colors: Record<string, string>;
	fonts: {serif: string; sans: string; mono: string};
	sizes: Record<string, number>;
	motion: {damping: number; stiffness: number; mass: number; dim_opacity: number; focus_scale: number; fade_frames: number};
};

export type SceneProps = {
	scene: TimelineScene;
	theme: Theme;
	progress: {durations: number[]; index: number};
};

// Pre-computed by scripts/prepare.mjs
export type CodeToken = {content: string; color: string; italic?: boolean};
