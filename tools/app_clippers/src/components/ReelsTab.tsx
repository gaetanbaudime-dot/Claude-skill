import Logo from "./Logo";

export default function ReelsTab() {
  return (
    <section className="apparait carte mt-2 px-6 py-12 flex flex-col items-center text-center">
      <Logo taille={64} />
      <h2 className="titre-argent text-xl font-bold mt-5">Le duplicateur de Reels arrive</h2>
      <p className="text-argent2 mt-2 max-w-xs leading-relaxed">Tes meilleurs Reels, déclinés en variantes prêtes à publier. On te prévient dès que c'est en ligne.</p>
      <span className="mt-6 text-[12px] font-semibold tracking-widest uppercase text-accent pulse">Bientôt</span>
    </section>
  );
}
