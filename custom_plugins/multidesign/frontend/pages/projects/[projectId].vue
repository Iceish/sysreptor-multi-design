<template>
  <v-container fluid>
    <h1>Outputs</h1>
    <p class="mb-4">Generate a PDF from the latest saved project content. Presentation designs use your written summaries; they do not summarize the report automatically.</p>
    <v-alert v-if="error" type="error" class="mb-4" role="alert">{{ error }}</v-alert>
    <v-btn v-if="!state && !loading" @click="load">Retry loading outputs</v-btn>
    <v-progress-linear v-if="loading" indeterminate aria-label="Loading outputs" />
    <template v-if="state">
      <v-alert v-if="state.hidden_choices" type="warning" class="mb-4">Some saved outputs use unavailable designs and are hidden. Saving replaces the visible output list.</v-alert>
      <v-select v-model="savedIndex" :items="savedItems" label="Saved output" clearable :disabled="busy" />
      <v-alert v-if="!state.choices.length" type="info" class="mb-4">No saved outputs yet. Choose a design and label, then save it for this project.</v-alert>
      <v-row>
        <v-col cols="12" md="6">
          <v-select v-model="designId" :items="designItems" label="Report design" :disabled="busy" />
        </v-col>
        <v-col cols="12" md="6">
          <v-text-field v-model="label" label="Output label" maxlength="100" :disabled="busy" />
        </v-col>
      </v-row>
      <v-text-field v-model="filename" label="Download filename (.pdf)" maxlength="184" :disabled="busy" />
      <v-alert v-if="!state.designs.length" type="info">No designs available. Ask your administrator for access to a report design.</v-alert>
      <v-alert v-if="issues.length" type="warning" class="mb-4">
        This design cannot render the source schema:
        <ul><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul>
      </v-alert>
      <div class="d-flex ga-3 flex-wrap mb-4">
        <v-btn color="primary" @click="render" :disabled="busy || !designId || !!issues.length" :loading="busy">{{ failed ? 'Retry PDF' : 'Generate PDF' }}</v-btn>
        <v-btn @click="save" :disabled="busy || !state.can_configure || !designId || !label.trim() || !validFilename">Save output</v-btn>
        <v-btn @click="remove" :disabled="busy || !state.can_configure || savedIndex === null">Remove saved output</v-btn>
        <v-btn @click="download" :disabled="busy || !pdfData || !validFilename">Download PDF</v-btn>
      </div>
      <p v-if="!state.can_configure" class="mb-3">Saving choices requires an editable project and project settings permission. PDF generation is available with project read access, as in SysReptor's report preview.</p>
      <p v-if="notice" role="status">{{ notice }}</p>
      <p v-if="busy" role="status">Capturing content and rendering PDF… {{ elapsed }} seconds. Large reports may take several minutes.</p>
      <p v-if="snapshotAt">Content snapshot: {{ snapshotAt }}. Generate again to include later edits.</p>
      <v-alert v-for="(message, i) in messages" :key="i" :type="message.level === 'error' ? 'error' : message.level === 'warning' ? 'warning' : 'info'" class="my-2">
        {{ message.message }} <span v-if="message.details">{{ message.details }}</span>
      </v-alert>
      <div v-if="pdfData" class="preview"><pdf :value="pdfData" /></div>
      <v-alert v-else-if="!busy && !failed" type="info" class="mt-4">Choose an output and generate a PDF to preview it here.</v-alert>
    </template>
  </v-container>
</template>

<script setup lang="ts">
type Choice = { label: string; design_id: string; filename: string };
type State = { project_name: string; designs: { id: string; name: string; current: boolean; issues: string[] }[]; choices: Choice[]; hidden_choices: number; can_configure: boolean };
type Message = { level: string; message: string; details?: string | null };
const route = useRoute();
const base = `/api/plugins/d42d1b7f-9c3b-4a62-a3f9-2d070d560127/api/projects/${route.params.projectId}`;
const state = ref<State | null>(null);
const loading = ref(false), busy = ref(false), failed = ref(false);
const error = ref(''), notice = ref(''), label = ref('Technical report'), filename = ref('report.pdf');
const designId = ref(''), savedIndex = ref<number | null>(null), pdfData = ref<string | null>(null);
const messages = ref<Message[]>([]), snapshotAt = ref(''), elapsed = ref(0);
const savedItems = computed(() => state.value?.choices.map((c, i) => ({ title: c.label, value: i })) || []);
const designItems = computed(() => state.value?.designs.map(d => ({ title: `${d.name}${d.current ? ' (current)' : ''}`, value: d.id })) || []);
const issues = computed(() => state.value?.designs.find(d => d.id === designId.value)?.issues || []);
const validFilename = computed(() => /^[^/\\\x00-\x1f\x7f]{1,180}\.pdf$/.test(filename.value));
watch(savedIndex, i => { const choice = i === null ? null : state.value?.choices[i]; if (choice) { designId.value = choice.design_id; label.value = choice.label; filename.value = choice.filename; } });
watch(designId, () => { pdfData.value = null; messages.value = []; snapshotAt.value = ''; failed.value = false; });

async function api(path: string, method = 'GET', body?: unknown): Promise<any> {
  const csrf = document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.slice('csrftoken='.length);
  const res = await fetch(`${base}/${path}/`, {
    method, credentials: 'same-origin', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': decodeURIComponent(csrf) } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    if (data.messages) messages.value = data.messages;
    throw new Error(data.compatibility?.join('\n') || data.detail || (data.messages ? 'PDF rendering failed. Review the messages and retry.' : JSON.stringify(data)));
  }
  return data;
}
async function load() {
  loading.value = true; error.value = '';
  try {
    state.value = await api('outputs');
    designId.value = state.value!.designs.find(d => d.current)?.id || state.value!.designs[0]?.id || '';
    filename.value = `${state.value!.project_name.replace(/[/\\\x00-\x1f\x7f]/g, '-').slice(0, 130) || 'report'}.pdf`;
  } catch (e) { error.value = String(e); }
  finally { loading.value = false; }
}
async function persist(choices: Choice[]) {
  busy.value = true; error.value = ''; notice.value = '';
  try { await api('outputs', 'PUT', { choices }); state.value!.choices = choices; notice.value = 'Output choices saved.'; }
  catch (e) { error.value = String(e); }
  finally { busy.value = false; }
}
async function save() {
  if (busy.value || !state.value) return;
  const choices = [...state.value.choices];
  const choice = { label: label.value.trim(), design_id: designId.value, filename: filename.value };
  if (savedIndex.value === null) choices.push(choice); else choices[savedIndex.value] = choice;
  await persist(choices);
}
async function remove() {
  if (busy.value || !state.value || savedIndex.value === null) return;
  const choices = state.value.choices.filter((_, i) => i !== savedIndex.value);
  await persist(choices); savedIndex.value = null;
}
async function render() {
  if (busy.value || !designId.value || issues.value.length) return;
  busy.value = true; failed.value = false; error.value = ''; notice.value = ''; pdfData.value = null; messages.value = []; snapshotAt.value = ''; elapsed.value = 0;
  const timer = window.setInterval(() => elapsed.value++, 1000);
  try {
    const result = await api('render', 'POST', { design_id: designId.value });
    pdfData.value = result.pdf; messages.value = result.messages; snapshotAt.value = result.snapshot_at;
  } catch (e) { error.value = String(e); failed.value = true; }
  finally { clearInterval(timer); busy.value = false; }
}
function download() {
  if (!pdfData.value || !validFilename.value) return;
  const bytes = Uint8Array.from(atob(pdfData.value), c => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
  const a = document.createElement('a'); a.href = url; a.download = filename.value; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
onMounted(load);
</script>

<style scoped>
.preview { height: 75vh; min-height: 400px; border: 1px solid #888; }
p { max-width: 90ch; }
</style>
