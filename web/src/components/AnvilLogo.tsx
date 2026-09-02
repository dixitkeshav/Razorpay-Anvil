export default function AnvilLogo({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <rect width="24" height="24" rx="6" fill="#0D5CFF" />
      <path
        d="M7 15.5 12 6l5 9.5-1.6.9L12 9.3 8.6 16.4 7 15.5Z"
        fill="white"
      />
      <path d="M8.4 17.2h7.2l-1 2H9.4l-1-2Z" fill="white" fillOpacity="0.85" />
    </svg>
  );
}
