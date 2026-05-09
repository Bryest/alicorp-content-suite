// Type declarations for non-TS imports
// (Next.js handles these natively at build time, but the TS checker
// needs explicit declarations to silence "Cannot find module" warnings.)

declare module "*.css";
declare module "*.scss";
declare module "*.sass";
declare module "*.module.css" {
  const classes: { readonly [key: string]: string };
  export default classes;
}
