import { Compass, MapPin, SlidersHorizontal } from 'lucide-react'

export function EmptyState() {
  return (
    <section className="empty-state" id="results" aria-labelledby="empty-title">
      <div className="empty-mark"><Compass size={25} /></div>
      <p className="eyebrow">No matching openings yet</p>
      <h2 id="empty-title">Widen the current.</h2>
      <p>No individual job pages matched every preference in this run. RoleCurrent does not pad the feed with generic career pages.</p>
      <div className="empty-suggestions">
        <span><MapPin size={15} /> Try Anywhere or Remote</span>
        <span><SlidersHorizontal size={15} /> Remove one keyword</span>
        <span><Compass size={15} /> Use a broader role title</span>
      </div>
      <a href="#search">Adjust search preferences</a>
    </section>
  )
}
