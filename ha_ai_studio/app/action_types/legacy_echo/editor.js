export function render(host, settings, context) {
  const p=document.createElement('p');p.textContent='This existing Echo instance uses the compatibility runtime. Echo returns your JSON data unchanged. Create new Echo instances from an action repository.';host.append(p);
  return ()=>({});
}
