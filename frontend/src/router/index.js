import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import Dashboard      from '../views/Dashboard.vue'
import WorkDetails    from '../views/WorkDetails.vue'
import ItemProgress   from '../views/ItemProgress.vue'
import AddNewWork     from '../views/AddNewWork.vue'
import UpdateWork     from '../views/UpdateWork.vue'
import MBDetails      from '../views/MBDetails.vue'
import Placeholder    from '../views/Placeholder.vue'
import Login           from '../views/Login.vue'
import Register        from '../views/Register.vue'
import ForgotPassword  from '../views/ForgotPassword.vue'
import UserManagement          from '../views/UserManagement.vue'
import InstallationCertificate from '../views/InstallationCertificate.vue'
import SiteRegister       from '../views/SiteRegister.vue'
import SiteGSheetSettings from '../views/SiteGSheetSettings.vue'
import SmtpSettings        from '../views/SmtpSettings.vue'
import TelegramSettings    from '../views/TelegramSettings.vue'
import TelegramLink           from '../views/TelegramLink.vue'
import SiteRegisterParties   from '../views/SiteRegisterParties.vue'
import AddSiteSupervisor     from '../views/AddSiteSupervisor.vue'

const routes = [
  { path: '/login',            name: 'Login',           component: Login,          meta: { public: true } },
  { path: '/register',         name: 'Register',        component: Register,       meta: { public: true } },
  { path: '/forgot-password',  name: 'ForgotPassword',  component: ForgotPassword, meta: { public: true } },

  { path: '/',                         name: 'Dashboard',        component: Dashboard },
  { path: '/work-details',             name: 'Work Details',     component: WorkDetails },
  { path: '/item-progress',            name: 'Item Progress',    component: ItemProgress },
  { path: '/add-new-work',             name: 'Add New Work',     component: AddNewWork },
  { path: '/update-work',              name: 'Update Work',      component: UpdateWork },
  { path: '/mb-details',               name: 'MB Details',       component: MBDetails },
  { path: '/site-register',               name: 'Site Register',            component: SiteRegister, meta: { siteRegisterAccess: true } },
  { path: '/settings/user-management',    name: 'User Management',          component: UserManagement,          meta: { adminOnly: true } },
  { path: '/settings/site-gsheet',        name: 'Site GSheet',              component: SiteGSheetSettings,      meta: { adminOnly: true } },
  { path: '/settings/smtp',               name: 'SMTP Settings',            component: SmtpSettings,            meta: { adminOnly: true } },
  { path: '/settings/telegram',           name: 'Telegram Settings',        component: TelegramSettings,        meta: { adminOnly: true } },
  { path: '/settings/telegram-link',          name: 'Link Rly Official Telegram', component: TelegramLink },
  { path: '/settings/site-register-parties', name: 'LOA Parties',                component: SiteRegisterParties, meta: { adminOnly: true } },
  { path: '/settings/add-supervisor',         name: 'Add Site Supervisor',        component: AddSiteSupervisor,   meta: { adminOnly: true } },
  { path: '/installation-certificate',   name: 'Installation Certificate', component: InstallationCertificate },
  { path: '/:pathMatch(.*)*',          name: 'Placeholder',      component: Placeholder },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

let authInitialized = false

router.beforeEach(async (to) => {
  const { state, fetchMe } = useAuth()

  if (!authInitialized) {
    await fetchMe()
    authInitialized = true
  }

  if (to.meta.public) {
    if (state.authenticated && (to.path === '/login' || to.path === '/register')) {
      return '/'
    }
    return true
  }

  if (!state.authenticated) {
    return '/login'
  }

  if (to.meta.adminOnly) {
    const isAdmin = state.user?.role === 'admin' || state.user?.is_staff
    if (!isAdmin) return '/'
  }

  if (to.meta.siteRegisterAccess) {
    const role    = state.user?.role
    const isAdmin = role === 'admin' || state.user?.is_staff
    if (!isAdmin && role !== 'consignee') return '/'
  }

  return true
})

export default router
