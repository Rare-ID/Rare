import rarePrimaryHorizontal from '../assets/rare-primary-horizontal.svg';

type BrandLogoProps = {
  className?: string;
  alt?: string;
};

export function BrandLogo({className = '', alt = 'RARE logo'}: BrandLogoProps) {
  return (
    <img
      src={rarePrimaryHorizontal}
      alt={alt}
      className={`w-auto object-contain invert ${className}`}
      loading="eager"
    />
  );
}
