/// <reference types="astro/client" />
/// <reference path="../.astro/types.d.ts" />

declare namespace JSX {
  interface IntrinsicElements {
    // Allow any JSX element
    [name: string]: any;
  }
}
