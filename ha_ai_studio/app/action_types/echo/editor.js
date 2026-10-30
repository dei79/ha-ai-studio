export function render(host, settings, context) {
  const p=document.createElement('p');p.textContent='Echo returns your JSON data unchanged. No additional settings are needed.';host.append(p);
  return ()=>({});
}
