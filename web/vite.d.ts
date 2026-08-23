import type { Plugin } from 'vite';
export interface ZanimViteOptions { typst?: string; cacheDir?: string; }
export declare function zanim(options?: ZanimViteOptions): Plugin;
export default zanim;
