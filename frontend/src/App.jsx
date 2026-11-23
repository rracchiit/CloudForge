
import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Activity, Boxes, ChevronDown, CircleHelp, Cloud, Code2,
  Container, GitBranch, LayoutDashboard, Plus, RefreshCw,
  Rocket, Server, Settings, Terminal, Zap, X, Loader2,
  ExternalLink, CheckCircle2, AlertCircle
} from 'lucide-react'

const API = '/api/v1'

const navigation = [
  {
    label: 'OVERVIEW',
    items: [
      { name: 'Dashboard', icon: LayoutDashboard },
      { name: 'Applications', icon: Boxes },
      { name: 'Deployments', icon: Rocket },
    ],
  },
  {
    label: 'INFRASTRUCTURE',
    items: [
      { name: 'Containers', icon: Container },
      { name: 'Logs', icon: Terminal },
    ],
  },
]

function App() {
  const [active, setActive] = useState('Dashboard')
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [repoUrl, setRepoUrl] = useState('')
  const [branch, setBranch] = useState('main')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const [deployingApp, setDeployingApp] = useState(null)
  const [deployStep, setDeployStep] = useState('')
  const [deployError, setDeployError] = useState('')
  const [deployResult, setDeployResult] = useState(null)
  const [deployHistory, setDeployHistory] = useState({})

  const [hostPort, setHostPort] = useState('')

  const [deployments, setDeployments] = useState([])
  const [deploymentsLoading, setDeploymentsLoading] = useState(false)
  const [deploymentsError, setDeploymentsError] = useState('')

  const loadApps = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await axios.get(`${API}/apps`)
      setApps(response.data)
    } catch (err) {
      console.error(err)
      setError('Could not connect to CloudForge API.')
    } finally {
      setLoading(false)
    }
  }

  const loadDeployments = async () => {
    try {
      setDeploymentsLoading(true)
      setDeploymentsError('')
      const response = await axios.get(`${API}/deployments/`)
      setDeployments(response.data)
    } catch (err) {
      console.error('Failed to load deployments:', err)
      setDeploymentsError('Failed to load deployments.')
    } finally {
      setDeploymentsLoading(false)
    }
  }


  const stopDeployment = async (id) => {
    try {
      await axios.post(`${API}/deployments/${id}/stop`)
      await loadDeployments()
    } catch (err) {
      console.error('Failed to stop deployment:', err)
      setDeploymentsError(err.response?.data?.detail || 'Failed to stop deployment.')
    }
  }


  const restartDeployment = async (id) => {
    try {
      await axios.post(`${API}/deployments/${id}/restart`)
      await loadDeployments()
    } catch (err) {
      console.error('Failed to restart deployment:', err)
      setDeploymentsError(err.response?.data?.detail || 'Failed to restart deployment.')
    }
  }


  const refreshDeploymentStatus = async (id) => {
    try {
      await axios.get(`${API}/deployments/${id}/status`)
      await loadDeployments()
    } catch (err) {
      console.error('Failed to refresh deployment status:', err)
    }
  }


  const openDeploymentLogs = async (id) => {
    try {
      const response = await axios.get(`${API}/deployments/${id}/logs`)
      window.alert(response.data.logs || 'No logs returned.')
    } catch (err) {
      console.error('Failed to fetch deployment logs:', err)
      window.alert(err.response?.data?.detail || 'Could not retrieve deployment logs.')
    }
  }


  useEffect(() => {
    loadApps()
    loadDeployments()
  }, [])

  const handleRegister = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setFormError('')

    try {
      const response = await axios.post(`${API}/apps`, {
        url: repoUrl.trim(),
        branch: branch.trim(),
      })

      setSuccessMessage(
        `Successfully registered ${response.data.owner}/${response.data.repo}`
      )

      setRepoUrl('')
      setBranch('main')
      setShowModal(false)
      await loadApps()
    } catch (err) {
      const detail = err.response?.data?.detail
      setFormError(
        typeof detail === 'string'
          ? detail
          : 'Registration failed. Check the repository URL and branch.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  const deployApplication = async (app) => {
    setDeployingApp(app)
    setDeployStep('Preparing deployment...')
    setDeployError('')
    setDeployResult(null)

    // App ID 4 uses port 8104, ID 5 uses 8105, etc.
    const selectedPort = 8100 + app.id
    setHostPort(String(selectedPort))

    try {
      // STEP 1: Check for an existing successful clone.
      setDeployStep('Checking cloned repositories...')

      let cloneExists = false

      try {
        const clonesResponse = await axios.get(`${API}/github/clones`)
        const clones = Array.isArray(clonesResponse.data)
          ? clonesResponse.data
          : []

        cloneExists = clones.some(clone =>
          clone.owner === app.owner &&
          clone.repo === app.repo &&
          clone.branch === app.branch &&
          clone.status === 'CLONED'
        )
      } catch {
        // If clone listing fails, attempt the clone endpoint.
        cloneExists = false
      }

      // STEP 2: Clone if required.
      if (!cloneExists) {
        setDeployStep('Cloning GitHub repository...')

        await axios.post(`${API}/github/clone`, {
          owner: app.owner,
          repo: app.repo,
          branch: app.branch,
        })
      }

      // STEP 3: Build Docker image.
      setDeployStep('Building Docker image...')

      const buildResponse = await axios.post(
        `${API}/deployments/build`,
        {
          application_id: app.id,
        }
      )

      const deploymentId = buildResponse.data.deployment_id

      if (!deploymentId) {
        throw new Error('Build succeeded but no deployment ID was returned.')
      }

      // STEP 4: Start Docker container.
      setDeployStep(`Starting container on port ${selectedPort}...`)

      const startResponse = await axios.post(
        `${API}/deployments/${deploymentId}/start`,
        {
          host_port: selectedPort,
          container_port: 8000,
        }
      )

      const result = {
        deploymentId,
        applicationId: app.id,
        imageName: buildResponse.data.image_name,
        imageId: buildResponse.data.image_id,
        containerId: startResponse.data.container_id,
        url: startResponse.data.deployment_url,
        status: startResponse.data.status,
        port: selectedPort,
      }

      setDeployResult(result)

      setDeployHistory(previous => ({
        ...previous,
        [app.id]: result,
      }))

      setDeployStep('Deployment completed successfully!')
      await loadDeployments()

    } catch (err) {
      console.error('Deployment error:', err)

      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Deployment failed. Check backend logs.'

      setDeployError(
        typeof detail === 'string'
          ? detail
          : 'Deployment failed. Check backend logs.'
      )

      setDeployStep('Deployment failed.')
    }
  }

  const runningCount = deployments.filter(
    deployment => deployment.status?.toUpperCase() === 'RUNNING'
  ).length

  const closeDeployModal = () => {
    setDeployingApp(null)
    setDeployStep('')
    setDeployError('')
    setDeployResult(null)
  }

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100">

      {/* SIDEBAR */}
      <aside className="fixed inset-y-0 left-0 z-20 flex w-64 flex-col border-r border-white/[0.07] bg-[#0c0c0f]">

        <div className="flex h-[72px] items-center gap-3 border-b border-white/[0.07] px-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-600 shadow-lg shadow-violet-900/30">
            <Cloud size={21} />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold">CloudForge</h1>
            <p className="text-[10px] tracking-[0.18em] text-zinc-500">
              DEVELOPER PLATFORM
            </p>
          </div>
        </div>

        <div className="px-4 py-6">
          {navigation.map(group => (
            <div key={group.label} className="mb-7">
              <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.16em] text-zinc-600">
                {group.label}
              </p>

              <div className="space-y-1">
                {group.items.map(item => {
                  const Icon = item.icon

                  return (
                    <button
                      key={item.name}
                      onClick={() => setActive(item.name)}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                        active === item.name
                          ? 'bg-violet-500/10 text-violet-300'
                          : 'text-zinc-400 hover:bg-white/[0.04] hover:text-white'
                      }`}
                    >
                      <Icon size={17} />
                      {item.name}

                      {item.name === 'Applications' && (
                        <span className="ml-auto rounded-md bg-white/[0.06] px-2 py-0.5 text-xs">
                          {apps.length}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-auto border-t border-white/[0.07] p-4">
          <button
            onClick={() => setActive('Settings')}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-zinc-400 hover:bg-white/[0.04]"
          >
            <Settings size={17} /> Settings
          </button>

          <div className="mt-4 flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-500/15 text-xs font-semibold text-violet-300">
              CF
            </div>
            <div>
              <p className="text-xs font-medium">CloudForge Workspace</p>
              <p className="text-[10px] text-zinc-500">Personal workspace</p>
            </div>
            <ChevronDown size={15} className="ml-auto text-zinc-500" />
          </div>
        </div>
      </aside>

      {/* MAIN */}
      <main className="min-h-screen pl-64">

        <header className="flex h-[72px] items-center justify-between border-b border-white/[0.07] px-8">
          <div>
            <p className="text-xs text-zinc-500">Workspace / {active}</p>
            <h2 className="mt-1 text-sm font-semibold">{active}</h2>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => { loadApps(); loadDeployments() }}
              className="rounded-lg border border-white/10 p-2 text-zinc-400 hover:bg-white/5"
              title="Refresh"
            >
              <RefreshCw size={16} />
            </button>

            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-xs font-semibold hover:bg-violet-500"
            >
              <Plus size={15} /> New application
            </button>
          </div>
        </header>

        <div className="mx-auto max-w-[1400px] p-8">

          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs text-violet-300">
                <Zap size={14} /> YOUR DEPLOYMENT WORKSPACE
              </div>

              <h1 className="text-3xl font-semibold tracking-tight">
                Build something <span className="text-zinc-500">great.</span>
              </h1>

              <p className="mt-2 text-sm text-zinc-500">
                Deploy, manage and monitor your applications.
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.02] px-3 py-2 text-xs text-zinc-400">
              <span className={`h-2 w-2 rounded-full ${
                error ? 'bg-red-400' : loading ? 'bg-yellow-400' : 'bg-emerald-400'
              }`} />
              {error ? 'API disconnected' : loading ? 'Connecting...' : 'API connected'}
            </div>
          </div>

          {successMessage && (
            <div className="mb-5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
              {successMessage}
            </div>
          )}

          {/* STATS */}
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { label: 'Applications', value: loading ? '—' : apps.length, icon: Boxes },
              { label: 'Running deployments', value: runningCount, icon: Activity },
              { label: 'Infrastructure', value: 'Docker', icon: Server },
            ].map(card => {
              const Icon = card.icon

              return (
                <div
                  key={card.label}
                  className="rounded-xl border border-white/[0.07] bg-[#111114] p-5"
                >
                  <div className="mb-5 flex items-center justify-between">
                    <span className="text-sm text-zinc-500">{card.label}</span>
                    <Icon size={17} className="text-zinc-500" />
                  </div>
                  <p className="text-2xl font-semibold">{card.value}</p>
                </div>
              )
            })}
          </div>

          {/* DEPLOYMENTS PAGE */}
          {active === 'Deployments' && (
            <section className="rounded-xl border border-white/[0.07] bg-[#111114] p-5">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold">All deployments</h3>
                  <p className="mt-1 text-xs text-zinc-500">Persistent deployments from your CloudForge database</p>
                </div>
                <button onClick={loadDeployments} className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400 hover:bg-white/5">
                  <RefreshCw size={14} /> Refresh
                </button>
              </div>
              {deploymentsLoading ? (
                <div className="py-10 text-center text-sm text-zinc-500">Loading deployments...</div>
              ) : deploymentsError ? (
                <div className="py-10 text-center text-sm text-red-400">{deploymentsError}</div>
              ) : deployments.length === 0 ? (
                <div className="py-10 text-center text-sm text-zinc-500">No deployments found.</div>
              ) : (
                <div className="space-y-3">
                  {deployments.map(deployment => {
                    const status = deployment.status?.toUpperCase() || 'UNKNOWN'
                    const isRunning = status === 'RUNNING'
                    return (
                      <div key={deployment.id} className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div>
                            <p className="text-sm font-medium">{deployment.owner}/{deployment.repo}</p>
                            <p className="mt-1 text-xs text-zinc-500">Deployment #{deployment.id} · {deployment.branch}</p>
                          </div>
                          <span className={`rounded-full border px-2.5 py-1 text-[10px] ${isRunning ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400' : status === 'FAILED' ? 'border-red-500/20 bg-red-500/10 text-red-400' : 'border-white/10 bg-white/5 text-zinc-400'}`}>{status}</span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-4 text-xs text-zinc-500">
                          <span>Host port: {deployment.host_port ?? '—'}</span>
                          <span>Container port: {deployment.container_port ?? '—'}</span>
                          <span>Container: {deployment.container_id ? deployment.container_id.slice(0, 12) : '—'}</span>
                        </div>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {deployment.deployment_url && isRunning && <a href={deployment.deployment_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg bg-violet-600 px-3 py-2 text-xs font-medium text-white hover:bg-violet-500">Open app <ExternalLink size={12} /></a>}
                          {isRunning ? <button onClick={() => stopDeployment(deployment.id)} className="rounded-lg border border-white/10 px-3 py-2 text-xs hover:bg-white/5">Stop</button> : deployment.container_id ? <button onClick={() => restartDeployment(deployment.id)} className="rounded-lg border border-white/10 px-3 py-2 text-xs hover:bg-white/5">Restart</button> : null}
                          <button onClick={() => refreshDeploymentStatus(deployment.id)} className="rounded-lg border border-white/10 px-3 py-2 text-xs hover:bg-white/5">Refresh status</button>
                          {deployment.container_id && <button onClick={() => openDeploymentLogs(deployment.id)} className="rounded-lg border border-white/10 px-3 py-2 text-xs hover:bg-white/5">View logs</button>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
          )}

          {/* APPLICATION LIST */}
          {active !== 'Deployments' && (
          <section className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#111114]">

            <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4">
              <div>
                <h3 className="text-sm font-semibold">Your applications</h3>
                <p className="mt-1 text-xs text-zinc-500">
                  GitHub repositories registered with CloudForge
                </p>
              </div>

              <button
                onClick={loadApps}
                className="text-xs text-zinc-400 hover:text-white"
              >
                Refresh
              </button>
            </div>

            {error ? (
              <div className="p-10 text-center text-sm text-red-300">
                {error}
              </div>
            ) : loading ? (
              <div className="p-10 text-center text-sm text-zinc-500">
                Loading applications...
              </div>
            ) : apps.length === 0 ? (
              <div className="p-12 text-center">
                <Code2 size={28} className="mx-auto mb-3 text-zinc-600" />
                <p className="text-sm font-medium">No applications yet</p>
              </div>
            ) : (
              <div className="divide-y divide-white/[0.06]">
                {apps.map(app => {
                  const deployment = deployHistory[app.id]

                  return (
                    <div
                      key={app.id}
                      className="flex flex-wrap items-center justify-between gap-4 px-5 py-4 hover:bg-white/[0.02]"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03]">
                          <GitBranch size={16} className="text-zinc-400" />
                        </div>

                        <div>
                          <p className="text-sm font-medium">
                            {app.owner}/{app.repo}
                          </p>
                          <p className="mt-1 text-xs text-zinc-500">
                            Branch: {app.branch} · App #{app.id}
                          </p>

                          {deployment?.url && (
                            <a
                              href={deployment.url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-1 inline-flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
                            >
                              Live application <ExternalLink size={11} />
                            </a>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        {deployment && (
                          <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] text-emerald-400">
                            {deployment.status}
                          </span>
                        )}

                        <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-zinc-300">
                          {app.status}
                        </span>

                        <button
                          onClick={() => deployApplication(app)}
                          disabled={!!deployingApp}
                          className="flex items-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Rocket size={13} />
                          {deployment ? 'Redeploy' : 'Deploy'}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          )}

          <footer className="mt-8 flex items-center justify-between text-[11px] text-zinc-600">
            <span>CloudForge · Deployment infrastructure</span>
            <span className="flex items-center gap-2">
              <CircleHelp size={13} /> Built for developers
            </span>
          </footer>
        </div>
      </main>

      {/* REGISTRATION MODAL */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#111114]">

            <div className="flex items-center justify-between border-b border-white/[0.07] px-6 py-5">
              <div>
                <h2 className="text-base font-semibold">New application</h2>
                <p className="mt-1 text-xs text-zinc-500">
                  Connect a GitHub repository
                </p>
              </div>

              <button onClick={() => setShowModal(false)}>
                <X size={18} />
              </button>
            </div>

            <form
              onSubmit={handleRegister}
              className="space-y-5 p-6"
            >
              <div>
                <label className="mb-2 block text-xs font-medium text-zinc-300">
                  Repository URL
                </label>
                <input
                  type="url"
                  required
                  value={repoUrl}
                  onChange={e => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/username/repository"
                  className="w-full rounded-lg border border-white/10 bg-[#09090b] px-4 py-3 text-sm outline-none focus:border-violet-500"
                />
              </div>

              <div>
                <label className="mb-2 block text-xs font-medium text-zinc-300">
                  Branch
                </label>
                <input
                  required
                  value={branch}
                  onChange={e => setBranch(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-[#09090b] px-4 py-3 text-sm outline-none focus:border-violet-500"
                />
              </div>

              {formError && (
                <p className="rounded-lg bg-red-500/10 p-3 text-xs text-red-300">
                  {formError}
                </p>
              )}

              <div className="flex justify-end gap-3 border-t border-white/[0.07] pt-5">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-white/10 px-4 py-2.5 text-xs"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-violet-600 px-5 py-2.5 text-xs font-semibold disabled:opacity-50"
                >
                  {submitting ? 'Registering...' : 'Register application'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DEPLOYMENT PROGRESS MODAL */}
      {deployingApp && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#111114] shadow-2xl">

            <div className="flex items-center justify-between border-b border-white/[0.07] px-6 py-5">
              <div>
                <h2 className="text-base font-semibold">
                  Deploy application
                </h2>
                <p className="mt-1 text-xs text-zinc-500">
                  {deployingApp.owner}/{deployingApp.repo}
                </p>
              </div>

              <button
                onClick={closeDeployModal}
                disabled={!deployResult && !deployError}
                className="text-zinc-500 hover:text-white disabled:opacity-30"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-5 p-6">

              {[
                'Cloning GitHub repository...',
                'Building Docker image...',
                `Starting container on port ${hostPort}...`,
              ].map((step, index) => {
                const complete =
                  deployResult ||
                  (
                    (index === 0 && deployStep !== 'Preparing deployment...' &&
                      deployStep !== 'Checking cloned repositories...' &&
                      deployStep !== 'Cloning GitHub repository...') ||
                    (index === 1 && deployStep.startsWith('Starting container')) ||
                    (index === 2 && deployResult)
                  )

                const failed = !!deployError

                return (
                  <div key={step} className="flex items-center gap-3">
                    {complete ? (
                      <CheckCircle2 size={19} className="text-emerald-400" />
                    ) : failed && index === 0 ? (
                      <AlertCircle size={19} className="text-red-400" />
                    ) : (
                      <Loader2 size={19} className="animate-spin text-violet-400" />
                    )}

                    <span className={`text-sm ${
                      complete ? 'text-emerald-300' : 'text-zinc-400'
                    }`}>
                      {step}
                    </span>
                  </div>
                )
              })}

              {!deployError && !deployResult && (
                <div className="rounded-lg border border-violet-500/20 bg-violet-500/10 p-4">
                  <p className="text-sm text-violet-200">{deployStep}</p>
                  <p className="mt-1 text-xs text-zinc-500">
                    Please keep this window open while CloudForge deploys your application.
                  </p>
                </div>
              )}

              {deployError && (
                <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
                  <p className="text-sm font-medium text-red-300">
                    Deployment failed
                  </p>
                  <p className="mt-2 break-words text-xs text-red-200">
                    {deployError}
                  </p>
                </div>
              )}

              {deployResult && (
                <div className="space-y-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4">
                  <div className="flex items-center gap-2 text-emerald-300">
                    <CheckCircle2 size={18} />
                    <span className="text-sm font-semibold">
                      Application is LIVE!
                    </span>
                  </div>

                  <div>
                    <p className="text-xs text-zinc-500">Deployment URL</p>
                    <a
                      href={deployResult.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-flex items-center gap-2 break-all text-sm text-emerald-300 hover:underline"
                    >
                      {deployResult.url}
                      <ExternalLink size={14} />
                    </a>
                  </div>

                  <div className="border-t border-emerald-500/10 pt-3 text-xs text-zinc-400">
                    <p>Deployment ID: {deployResult.deploymentId}</p>
                    <p className="mt-1">Host port: {deployResult.port}</p>
                    <p className="mt-1 break-all">
                      Image: {deployResult.imageName}
                    </p>
                    <p className="mt-1 break-all">
                      Container: {deployResult.containerId}
                    </p>
                  </div>
                </div>
              )}

              {(deployResult || deployError) && (
                <div className="flex justify-end border-t border-white/[0.07] pt-4">
                  <button
                    onClick={closeDeployModal}
                    className="rounded-lg bg-violet-600 px-5 py-2.5 text-xs font-semibold hover:bg-violet-500"
                  >
                    Close
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
