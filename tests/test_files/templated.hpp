#include <vector>

class T 
{
    private:
        int _i;
    public:

        T(const T& t){
        _i = t._i;
        };

        T(int i): _i(i) { };
        int get() const {
            return _i;
        }
};

template <class X>
class Templated {

    private:
        X _x;

    public:

        Templated(X x): _x(x) { };

        Templated(const Templated<X> & t): _x(t._x) { };

        X get() const
        {
            return _x;
        }

        int getTwice(const Templated<X> &ti) const
        {
            return ti.get().get();
        }


        int summup(std::vector<Templated<X> > &v)
        {
            int sum = 0;
            for (typename std::vector<Templated<X> >::const_iterator it=v.begin(); it != v.end(); ++it)
            {
                sum += it->get().get();
            }
            v.push_back(Templated(X(11)));
            return sum;

        };
        std::vector<Templated<X> > reverse(std::vector<Templated<X> > &v)
        {
            return std::vector<Templated<X> >(v.rbegin(), v.rend());
        };

        Templated<X> passs(Templated<X> &v)
        {
            return v;
        }

};


class Y  {

    public:
        std::vector<Templated<T> > passs(std::vector<Templated<T> > &x)
        {
            return x;
        };
};


