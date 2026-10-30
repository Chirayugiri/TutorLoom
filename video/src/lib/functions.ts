// Activation functions plotted by compare_cards. Values are computed here, never typed by the LLM.
export type FnName = 'step' | 'sigmoid' | 'tanh' | 'relu' | 'leaky_relu' | 'gelu' | 'softplus' | 'identity';

const erf = (x: number): number => {
	// Abramowitz–Stegun 7.1.26
	const t = 1 / (1 + 0.3275911 * Math.abs(x));
	const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
	return x >= 0 ? y : -y;
};

export const FNS: Record<FnName, (x: number) => number> = {
	step: (x) => (x >= 0 ? 1 : 0),
	sigmoid: (x) => 1 / (1 + Math.exp(-x)),
	tanh: (x) => Math.tanh(x),
	relu: (x) => Math.max(0, x),
	leaky_relu: (x) => (x >= 0 ? x : 0.1 * x),
	gelu: (x) => 0.5 * x * (1 + erf(x / Math.SQRT2)),
	softplus: (x) => Math.log1p(Math.exp(x)),
	identity: (x) => x,
};

// Points where the function jumps (the plotted path is broken there).
export const DISCONTINUITIES: Partial<Record<FnName, number[]>> = {step: [0]};

export const DEFAULT_Y: Record<FnName, [number, number]> = {
	step: [-0.45, 1.45],
	sigmoid: [-0.45, 1.45],
	tanh: [-1.45, 1.45],
	relu: [-0.9, 3.1],
	leaky_relu: [-0.9, 3.1],
	gelu: [-0.9, 3.1],
	softplus: [-0.9, 3.1],
	identity: [-3.1, 3.1],
};
