declare module 'aladin-lite' {
  interface AladinOptions {
    target?: string;
    fov?: number;
    survey?: string;
    showReticle?: boolean;
    showZoomControl?: boolean;
    showFullscreenControl?: boolean;
    showLayersControl?: boolean;
    showGotoControl?: boolean;
    cooFrame?: string;
    [key: string]: any;
  }

  interface AladinInstance {
    gotoRaDec: (ra: number, dec: number) => void;
    getRaDec: () => [number, number];
    setImageSurvey: (survey: string) => void;
    on: (event: string, callback: (...args: any[]) => void) => void;
    destroy?: () => void;
    [key: string]: any;
  }

  interface AladinGlobal {
    init: Promise<void>;
    aladin: (container: HTMLElement | string, options?: AladinOptions) => AladinInstance;
    [key: string]: any;
  }

  const A: AladinGlobal;
  export default A;
}
