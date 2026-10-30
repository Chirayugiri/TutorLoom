import {loadFont as loadSerif} from '@remotion/google-fonts/SourceSerif4';
import {loadFont as loadBaskerville} from '@remotion/google-fonts/LibreBaskerville';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';

// Loaded once per bundle; Remotion waits for them before capturing frames.
loadSerif('normal', {weights: ['400', '600'], subsets: ['latin']});
loadSerif('italic', {weights: ['400'], subsets: ['latin']});
loadBaskerville('normal', {weights: ['400', '700'], subsets: ['latin']});
loadInter('normal', {weights: ['400', '500', '600'], subsets: ['latin']});
loadMono('normal', {weights: ['400', '600'], subsets: ['latin']});
