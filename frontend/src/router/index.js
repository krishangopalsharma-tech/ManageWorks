import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import Dashboard      from '../views/Dashboard.vue'
import WorkDetails    from '../views/WorkDetails.vue'
import ItemProgress   from '../views/ItemProgress.vue'
import AddNewWork     from '../views/AddNewWork.vue'
import UpdateWork     from '../views/UpdateWork.vue'
import MBDetails      from '../views/MBDetails.vue'
import Placeholder    from '../views/Placeholder.vue'
import Login          from '../views/Login.vue'
import Register       from '../views/Register.vue'
import UserManagement          from '../views/UserManagement.vue'
import InstallationCertificate from '../views/InstallationCertificate.vue'

const routes = [
  { path: '/login',    name: 'Login',    component: Login,    meta: { public: true } },
  { path: '/register', name: 'Register', component: Register, meta: { public: true } },

  { path: '/',                         name: 'Dashboard',        component: Dashboard },
  { path: '/work-details',             name: 'Work Details',     component: WorkDetails },
  { path: '/item-progress',            name: 'Item Progress',    component: ItemProgress },
  { path: '/add-new-work',             name: 'Add New Work',     component: AddNewWork },
  { path: '/update-work',              name: 'Update Work',      component: UpdateWork },
  { path: '/mb-details',               name: 'MB Details',       component: MBDetails },
  { path: '/settings/user-management',    name: 'User Management',          component: UserManagement,          meta: { adminOnly: true } },
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

  return true
})

export default router
