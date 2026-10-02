import type { JSX } from "react";
import { useTranslation } from "react-i18next";
import logoUrl from "@/assets/krtr-logo.png";

/**
 * The krtr logo followed by its wordmark, as shown at the left of every header.
 *
 * Exists as the single brand lockup shared by the public landing header and
 * the authenticated app header.
 *
 * @returns The logo image and the "krtr" wordmark.
 */
export function BrandMark(): JSX.Element {
  const { t } = useTranslation();
  return (
    <span className="mr-auto flex items-center gap-2 font-heading text-[22px] font-extrabold tracking-[-0.02em]">
      <img src={logoUrl} alt="" className="block h-9 w-auto" />
      <span>{t("app_name")}</span>
    </span>
  );
}

/**
 * The large logo illustration used on the landing page's right column.
 *
 * @returns The decorative logo image.
 */
export function BrandIllustration(): JSX.Element {
  return <img src={logoUrl} alt="" className="block h-auto w-full max-w-[560px]" />;
}
