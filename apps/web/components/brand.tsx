export function Logo({ large = false }: { large?: boolean }) {
  return (
    <div className={`brand ${large ? 'large' : ''}`}>
      <img src="/favicon.svg" alt="" width={large ? 55 : 40} height={large ? 55 : 40} />
      <span>Lumvia</span>
    </div>
  );
}
