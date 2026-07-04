export interface Testimonial {
  id: string;
  name: string;
  role: string;
  company: string;
  avatarUrl: string;
  rating: number;
  text: string;
  gradient: string;
}

export const testimonials: Testimonial[] = [
  {
    id: "testimonial-1",
    name: "Sarah Jenkins",
    role: "Chief Financial Officer",
    company: "Apex Global",
    avatarUrl: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=150&h=150&q=80",
    rating: 5,
    text: "Migrating our multinational finance entries to Prime has reduced our month-end close time from 12 days to just 36 hours. The AI financial anomaly detection flagged a duplicate payment error on day one, saving us over $48,000.",
    gradient: "from-blue-500/10 to-indigo-500/10"
  },
  {
    id: "testimonial-2",
    name: "Marcus Thorne",
    role: "VP of Supply Chain",
    company: "Logix Logistics",
    avatarUrl: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&w=150&h=150&q=80",
    rating: 5,
    text: "The demand-forecasting accuracy of the smart inventory module is staggering. We decreased our safety stock holding cost by 22% while improving our prompt fulfillment rate to a perfect 99.8%. The supply-chain automation is game-changing.",
    gradient: "from-cyan-500/10 to-blue-500/10"
  },
  {
    id: "testimonial-3",
    name: "Elena Rostova",
    role: "Director of HR Operations",
    company: "Velo Technologies",
    avatarUrl: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=150&h=150&q=80",
    rating: 5,
    text: "Onboarding employees across four countries was a regulatory nightmare. This system automatically adapts payroll structures and dynamic compliance forms to regional rules instantly. Our team productivity is up 40%.",
    gradient: "from-violet-500/10 to-fuchsia-500/10"
  },
  {
    id: "testimonial-4",
    name: "David Chen",
    role: "Chief Operating Officer",
    company: "Aura Manufacturing",
    avatarUrl: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=150&h=150&q=80",
    rating: 5,
    text: "The unified manufacturing MRP dashboard has given us true visibility into shop-floor performance. We can build custom bill-of-materials and track telemetry instantly. Highly recommended for any serious operation.",
    gradient: "from-emerald-500/10 to-teal-500/10"
  }
];
