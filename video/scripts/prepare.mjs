// Pre-render step: syntax-highlight code with Shiki and typeset formulas with KaTeX,
// so the Remotion components stay synchronous and deterministic.
// usage: node scripts/prepare.mjs props1.json [props2.json ...]   (files are rewritten in place)
import fs from 'node:fs';
import katex from 'katex';
import {createHighlighter} from 'shiki';

const files = process.argv.slice(2);
if (!files.length) process.exit(0);

const tex = (src, display = false) =>
	katex.renderToString(src, {throwOnError: false, displayMode: display, trust: true, strict: 'ignore', output: 'html'});

let highlighter = null;
const themeFor = (c) => ({
	name: 'n2v',
	type: 'dark',
	colors: {'editor.foreground': c.code_text, 'editor.background': c.card},
	tokenColors: [
		{scope: ['comment', 'punctuation.definition.comment'], settings: {foreground: c.code_comment, fontStyle: 'italic'}},
		{scope: ['string', 'string.quoted', 'punctuation.definition.string'], settings: {foreground: c.code_string}},
		{scope: ['constant.numeric', 'constant.language'], settings: {foreground: c.code_number}},
		{scope: ['keyword', 'storage', 'keyword.operator.logical', 'storage.type'], settings: {foreground: c.code_keyword, fontStyle: 'bold'}},
		{scope: ['entity.name.function', 'support.function', 'meta.function-call.generic'], settings: {foreground: c.code_function}},
		{scope: ['variable', 'meta.function-call.arguments'], settings: {foreground: c.code_text}},
	],
});

for (const file of files) {
	const props = JSON.parse(fs.readFileSync(file, 'utf8'));
	const {scene, theme} = props;
	const content = scene.content;
	if (scene.template === 'code' && content.code) {
		const lang = content.language ?? 'python';
		highlighter ??= await createHighlighter({themes: [themeFor(theme.colors)], langs: ['python', 'javascript', 'typescript', 'bash']});
		const lines = highlighter.codeToTokensBase(content.code.replace(/\n$/, ''), {lang, theme: 'n2v'});
		content.tokens = lines.map((line) =>
			line.map((t) => ({content: t.content, color: t.color ?? theme.colors.code_text, italic: Boolean((t.fontStyle ?? 0) & 1)})),
		);
	}
	for (const card of content.cards ?? []) {
		if (card.formula) card.formula_html = tex(card.formula);
	}
	if (content.latex) content.latex_html = tex(content.latex, true);
	fs.writeFileSync(file, JSON.stringify(props));
}
